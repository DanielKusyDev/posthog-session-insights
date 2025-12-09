"""
Simple dummy client that reads events from sample_events.json and sends them in a random order to the ingestion endpoint
in "waves" of various frequency and number of batches. It's meant to simulate real, unpredictable traffic from users.
"""
import asyncio
import json
import random
import time
from datetime import datetime
from pathlib import Path

import httpx


class DummyClient:
    def __init__(
        self,
        url: str = "http://127.0.0.1:8000/ingest",
        events_file: str = "sample_events.json",
        duration_seconds: int = 120,
        max_concurrent: int = 50,
        use_traffic_waves: bool = True,
    ):
        self.url = url
        self.events_file = Path(events_file)
        self.duration_seconds = duration_seconds
        self.max_concurrent = max_concurrent
        self.use_traffic_waves = use_traffic_waves

        self.events = []
        self.stats = {
            "total_sent": 0,
            "success": 0,
            "failed": 0,
            "errors": [],
            "start_time": None,
            "end_time": None,
            "current_wave": 0,
            "current_rps": 0,
        }
        
        # Traffic wave patterns: (min_rps, max_rps, duration_seconds)
        self.traffic_waves = [
            (15, 25, random.uniform(8, 15)),    # Fast burst
            (3, 7, random.uniform(10, 20)),     # Slow period
            (1, 2, random.uniform(5, 10)),      # Very slow
            (20, 35, random.uniform(8, 12)),    # High traffic
            (5, 10, random.uniform(8, 15)),     # Medium
            (1, 3, random.uniform(5, 8)),       # Slow again
            (25, 40, random.uniform(10, 15)),   # Peak traffic
        ]

    def load_events(self):
        """Load sample events from JSON file."""
        with open(self.events_file, "r") as f:
            self.events = json.load(f)
        print(f"Loaded {len(self.events)} sample events")

    def get_random_event(self):
        """Get a random event and update its timestamp to now."""
        event = random.choice(self.events).copy()
        # Update timestamp to current time for more realistic data
        event["timestamp"] = datetime.now().isoformat()
        return event

    async def send_event(self, client: httpx.AsyncClient, event: dict):
        """Send a single event to the API."""
        try:
            response = await client.post(self.url, json={"event": event}, timeout=10.0)
            if response.status_code == 202:
                self.stats["success"] += 1
            else:
                self.stats["failed"] += 1
                self.stats["errors"].append({
                    "status": response.status_code,
                    "error": response.text[:200]
                })
        except httpx.TimeoutException:
            self.stats["failed"] += 1
            self.stats["errors"].append({"error": "Timeout"})
        except Exception as e:
            self.stats["failed"] += 1
            self.stats["errors"].append({"error": str(e)[:200]})
        finally:
            self.stats["total_sent"] += 1

    async def worker(self, client: httpx.AsyncClient, queue: asyncio.Queue):
        """Worker coroutine that processes events from the queue."""
        while True:
            event = await queue.get()
            if event is None:  # Sentinel value to stop worker
                queue.task_done()
                break

            await self.send_event(client, event)
            queue.task_done()

            # Add small random delay to simulate more realistic traffic patterns
            await asyncio.sleep(random.uniform(0.001, 0.01))

    async def producer(self, queue: asyncio.Queue):
        """Producer coroutine that generates events with dynamic traffic waves."""
        end_time = time.time() + self.duration_seconds
        wave_index = 0
        wave_start = time.time()
        
        if self.use_traffic_waves:
            min_rps, max_rps, wave_duration = self.traffic_waves[wave_index]
            current_rps = random.uniform(min_rps, max_rps)
            print(f"\nStarting wave {wave_index + 1}: {current_rps:.1f} req/s for ~{wave_duration:.1f}s")
        else:
            current_rps = 10  # Fallback constant rate
            wave_duration = self.duration_seconds
        
        self.stats["current_rps"] = current_rps
        self.stats["current_wave"] = wave_index

        while time.time() < end_time:
            # Check if we need to switch to next wave
            if self.use_traffic_waves and (time.time() - wave_start) >= wave_duration:
                wave_index = (wave_index + 1) % len(self.traffic_waves)
                wave_start = time.time()
                min_rps, max_rps, wave_duration = self.traffic_waves[wave_index]
                current_rps = random.uniform(min_rps, max_rps)
                self.stats["current_rps"] = current_rps
                self.stats["current_wave"] = wave_index
                print(f"\n→ Switching to wave {wave_index + 1}: {current_rps:.1f} req/s for ~{wave_duration:.1f}s")
            
            start = time.time()
            interval = 1.0 / current_rps

            # Add event to queue
            event = self.get_random_event()
            await queue.put(event)

            # Sleep to maintain the current rate
            elapsed = time.time() - start
            sleep_time = max(0, interval - elapsed)
            await asyncio.sleep(sleep_time)

        print("\nProducer finished. Waiting for workers to complete...")

    async def run(self):
        """Main run method that orchestrates the load test."""
        self.load_events()
        self.stats["start_time"] = time.time()

        print(f"\nStarting load test:")
        print(f"  URL: {self.url}")
        print(f"  Mode: {'Dynamic traffic waves' if self.use_traffic_waves else 'Constant rate'}")
        print(f"  Duration: {self.duration_seconds} seconds")
        print(f"  Concurrent workers: {self.max_concurrent}\n")

        queue = asyncio.Queue(maxsize=self.max_concurrent * 2)

        async with httpx.AsyncClient() as client:
            # Start workers
            workers = [
                asyncio.create_task(self.worker(client, queue))
                for _ in range(self.max_concurrent)
            ]

            # Start producer
            producer_task = asyncio.create_task(self.producer(queue))

            # Progress reporter
            async def report_progress():
                while not producer_task.done():
                    await asyncio.sleep(5)
                    elapsed = time.time() - self.stats["start_time"]
                    rate = self.stats["total_sent"] / elapsed if elapsed > 0 else 0
                    current_rps = self.stats.get('current_rps', 0)
                    wave_num = self.stats.get('current_wave', 0) + 1
                    print(
                        f"Progress: {self.stats['total_sent']} sent "
                        f"({self.stats['success']} success, {self.stats['failed']} failed) "
                        f"- Actual: {rate:.1f} req/s | Target: {current_rps:.1f} req/s (Wave {wave_num})"
                    )

            reporter = asyncio.create_task(report_progress())

            # Wait for producer to finish
            await producer_task

            # Wait for queue to be empty
            await queue.join()

            # Stop workers
            for _ in range(self.max_concurrent):
                await queue.put(None)
            await asyncio.gather(*workers)

            # Stop reporter
            reporter.cancel()
            try:
                await reporter
            except asyncio.CancelledError:
                pass

        self.stats["end_time"] = time.time()
        self.print_summary()

    def print_summary(self):
        """Print summary statistics."""
        duration = self.stats["end_time"] - self.stats["start_time"]
        actual_rate = self.stats["total_sent"] / duration if duration > 0 else 0
        success_rate = (self.stats["success"] / self.stats["total_sent"] * 100) if self.stats["total_sent"] > 0 else 0

        print("\n" + "="*60)
        print("LOAD TEST SUMMARY")
        print("="*60)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Total requests sent: {self.stats['total_sent']}")
        print(f"Successful: {self.stats['success']} ({success_rate:.1f}%)")
        print(f"Failed: {self.stats['failed']}")
        print(f"Average rate: {actual_rate:.1f} requests/second")

        if self.stats["errors"]:
            print(f"\nFirst 5 errors:")
            for error in self.stats["errors"][:5]:
                print(f"  - {error}")

        print("="*60)


async def main():
    # Configuration
    client = DummyClient(
        url="http://api:8000/ingest",  # Use docker service name
        events_file="sample_events.json",
        duration_seconds=120,  # Run for 2 minutes
        max_concurrent=50,
        use_traffic_waves=True,  # Enable dynamic traffic patterns
    )

    await client.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nLoad test interrupted by user")
