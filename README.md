## Event Classification

The enrichment pipeline classifies PostHog events into structured types to make them LLM-friendly.

### Classification Strategy

Every raw event is classified into two dimensions:

1. **Event Type** - High-level category (pageview, click, navigation, custom, unknown)
2. **Action Type** - Specific user action (view, click, submit, rage_click, etc.)

### PostHog System Events

| Event Name | Event Type | Action Type | Notes |
|------------|-----------|-------------|-------|
| `$pageview` | pageview | view | User viewed a page |
| `$pageleave` | navigation | leave | User left a page |
| `$rageclick` | click | rage_click | User clicked repeatedly (frustration signal) |
| `$autocapture` | click | varies | Depends on `properties.$event_type` |

### Autocapture Classification

`$autocapture` events are further classified based on `properties.$event_type`:
```python
properties.$event_type == "click"   → (click, click)
properties.$event_type == "submit"  → (click, submit)
properties.$event_type == "change"  → (click, change)
# Default if missing or unknown
properties.$event_type == <missing> → (click, click)
```

### Custom Events

Custom events (no `$` prefix) are classified as `event_type=custom` with inferred `action_type` based on heuristics:

| Pattern in Event Name | Inferred Action Type | Examples |
|----------------------|---------------------|----------|
| click, select, choose | click | `product_clicked`, `item_selected` |
| submit, complete, finish | submit | `form_submitted`, `payment_completed` |
| start, open, view, navigate | navigate | `upgrade_started`, `page_viewed` |
| *no match* | click (default) | `random_event` |

**Example:**
```python
classify_event("product_clicked", {})
# → EventClassification(event_type="custom", action_type="click")

classify_event("plan_upgrade_started", {})
# → EventClassification(event_type="custom", action_type="navigate")
```

### Unknown Events

Unknown PostHog system events (e.g., `$unknown_future_event`) are classified as:
- `event_type=unknown`
- `action_type=unknown`

This ensures the pipeline doesn't break when PostHog introduces new event types.

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