## 🔧 Design & Build Challenge — Senior Data Pipeline & Backend Engineer

### 🎯 Goal

Design **and** implement a production-minded system that can:

- In **real time**, ingest **PostHog event data** (clicks, pageviews, feature usage),
- **Normalize & enrich** this stream into a clean, structured, LLM-friendly format,
- And expose that enriched user interaction data as **context for an AI chatbot**, so the bot can use user behaviour to improve **RAG retrieval, responses, and provide proactive recommendations**.

You should build an actual **POC**, and then describe **how you’d scale that POC to production** for a real SaaS product.

---

## 1. **Build a POC**

Use **PostHog Autocapture**

https://posthog.com/docs/product-analytics/autocapture

Capture at least:

- Pageviews
- Click events (autocapture or custom events)
- Named feature-usage events
- Enough raw data to reconstruct simple “sessions”

We want a **minimal but working vertical slice** of this pipeline.

### Your POC should:

### **1. Ingest PostHog events in (near) real time**

- You may use webhooks, PostHog’s API, or a mock ingestion endpoint that simulates the flow.
- Events should arrive continuously and be stored in **raw** form.

### **2. Normalize & structure events into an LLM-friendly schema**

E.g., group by:

- `user_id`
- `session_id`
- chronological `events[]`

With semantic enrichment such as:

- readable labels (e.g. “Clicked Upgrade button”)
- page → component → element hierarchy
- timestamps, ordering, etc.

### **3. Produce context objects for an AI chatbot / RAG pipeline**

Example context outputs:

- **Recent activity:** last N events
- **Session snapshot:** short summary of the user’s latest session
- **Aggregated patterns:** e.g. “User repeatedly opened billing page but never completed plan selection”

These should be returned as **structured JSON the chatbot can drop into a prompt**.

### **4. Expose a simple API endpoint**, e.g.:

`GET /context/user/{user_id}` → returns

```json
{
  "recent_events": [...],
  "last_session_summary": "...",
  "patterns": [...]
}

```

Focus on:

- Clean structure
- Readable code
- Clear separation of concerns

A simple in-memory DB (SQLite / Postgres / Redis / even a dict) is fine for the POC.

---

## 2. **Describe how you’d scale this POC to production**

After building the thin slice, how would you make this production ready to handle thousands of users using the software at one time?