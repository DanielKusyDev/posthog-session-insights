"""
Simple dummy client that reads events from sample_events.json and sends them
sequentially to the ingestion endpoint as fast as possible.
"""

import asyncio
import json
import time
from pathlib import Path

import httpx


async def send_event(client: httpx.AsyncClient, event: dict, url: str, index: int) -> bool:
    """Send a single event to the ingestion endpoint."""
    try:
        response = await client.post(url, json={"event": event}, timeout=5.0)
        success = 200 <= response.status_code < 400
        status = "✓" if success else "✗"
        print(f"{status} Event {index + 1}: {response.status_code}")
        return success
    except Exception as e:
        print(f"✗ Event {index + 1}: Error - {e}")
        return False


async def main():
    # Load events from sample file
    events_file = Path(__file__).parent / "sample_events.json"

    print(f"Loading events from {events_file}")
    with open(events_file) as f:
        data = json.load(f)
        events = data if isinstance(data, list) else [data]

    print(f"Loaded {len(events)} events\n")

    # Target endpoint
    url = "http://api:8000/ingest"
    print(f"Sending to: {url}\n")

    start_time = time.time()
    successful = 0

    async with httpx.AsyncClient() as client:
        for i, event in enumerate(events):
            success = await send_event(client, event, url, i)
            if success:
                successful += 1

    duration = time.time() - start_time
    success_rate = (successful / len(events) * 100) if events else 0

    print(f"\nComplete!")
    print(f"Sent: {len(events)} events")
    print(f"Successful: {successful} ({success_rate:.1f}%)")
    print(f"Duration: {duration:.2f}s")
    print(f"Rate: {len(events) / duration:.1f} events/second")


if __name__ == "__main__":
    asyncio.run(main())
