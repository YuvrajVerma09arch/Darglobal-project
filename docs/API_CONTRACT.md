# API Contract — single source of truth for frontend / backend / infra

Base URL (local): `http://localhost:8000`
Prefix: `/api/v1`
All request/response bodies are JSON except streaming chat (SSE).

## `GET /health`
```json
{"status":"ok","version":"1.0.0","database":"connected","indexed_chunks":123,"last_ingest_at":null}
```

## `GET /api/v1/sources`
```json
{"sources":[{"source":"darglobal","records":42,"chunks":180,"last_scraped_at":"2026-..."}],"generated_at":"..."}
```

## `GET /api/v1/stats`
```json
{"records":0,"chunks":0,"sources":{},"property_types":{},"cities":{},"last_scraped_at":null,"last_ingestion":null}
```

## `POST /api/v1/chat`
Request:
```json
{
  "message": "Show me 3 bedroom apartments in Riyadh under 2 million SAR",
  "conversation_id": "abc123",
  "source_filter": "both",
  "filters": {
    "location": null, "city": null, "property_type": null,
    "listing_type": null, "min_price": null, "max_price": null,
    "bedrooms": null, "bathrooms": null
  },
  "stream": false
}
```
Non-streaming response `ChatResponse`:
```json
{
  "answer": "...",
  "conversation_id": "abc123",
  "citations": [{
    "record_id":"r_...","source":"wasalt","title":"...","url":"https://...",
    "snippet":"...","score":0.032,"document_type":"property",
    "location":"Riyadh","price":1800000,"currency":"SAR",
    "bedrooms":3,"bathrooms":2,"area":150,"image_urls":[]
  }],
  "records": [/* same shape as PropertyOut, one per citation */],
  "retrieved_count": 6,
  "query_type": "listing",
  "filters_applied": {"city":"Riyadh","bedrooms":3,"max_price":2000000},
  "data_as_of": "2026-...",
  "model": "openai/gpt-4o-mini",
  "warnings": []
}
```
Streaming (`stream: true`) uses `text/event-stream`:
```
event: token
data: {"text":"The "}

event: done
data: { ...full ChatResponse JSON... }

event: error
data: {"detail":"..."}
```
The frontend must always read the `done` event to get citations, records and conversation_id.

## `GET /api/v1/properties`
Query params: `source=darglobal|wasalt|both`, `location`, `city`, `property_type`, `min_price`, `max_price`, `bedrooms`, `limit` (default 24, max 100), `offset`.
Response `PropertyListResponse`: `{"items":[PropertyOut],"total":N,"limit":24,"offset":0}`.
PropertyOut fields: `id, source, title, description, property_type, location, city, country, price, currency, bedrooms, bathrooms, area, area_unit, amenities[], project_status, image_urls[], source_url, scraped_at, document_type`.

## `GET /api/v1/properties/{id}`
Returns a single `PropertyOut` (404 if missing).

## `POST /api/v1/search`
Request: `{"query":"...","source_filter":"both","filters":{...},"top_k":8}`
Response: `{"results":[{"citation":{...},"semantic_score":0.3,"structured_match":false}],"query_type":"listing","filters_applied":{},"data_as_of":null}`

## `POST /api/v1/admin/ingest`
Header `X-Admin-Key: <ADMIN_API_KEY>`. Body optional `{"source":"both"|"darglobal"|"wasalt"}`.
Response `IngestResponse`.

## Errors
FastAPI standard: `{"detail":"..."}` with 400/401/404/422/429/500. Never expose stack traces.

## Frontend env
`VITE_API_BASE_URL` (default `http://localhost:8000`). No API keys in frontend.
