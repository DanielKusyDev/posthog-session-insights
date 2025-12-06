## Error Handling & Retry Logic

POC: Failed events require manual review/reset.

Production approach:
- Exponential backoff with max 3 retries
- Dead letter queue for permanent failures
- Alerting on DEAD_LETTER status
- Separate worker for DLQ processing


## Scaling to Production

Current POC uses database as queue (simple, transactional).
For production scale (1000s events/sec), I'd migrate to:

1. **Event ingestion:**
   - API saves to raw_event (source of truth)
   - Publishes to RabbitMQ/Azure Service Bus/AWS SQS/GCP Sub/Kafka topic

2. **Processing:**
   - Workers consume from the broker
   - Process & save enriched events
   - Message broker handles retries, DLQ, backpressure

3. **Benefits:**
   - 10-100x better throughput
   - Built-in retry logic
   - Horizontal scaling (add workers instantly)
   - Better observability (e.g. RabbitMQ UI)

4. **Tradeoffs:**
   - More infrastructure complexity
   - Need to handle dual-write consistency