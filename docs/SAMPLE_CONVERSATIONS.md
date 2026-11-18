# Sample conversations (local verification, 2026-11-18)

These transcripts show the retrieval/grounding contract. The LLM key was not
present on the build machine, so the "answer" text in generation-enabled runs is
represented by the exact fallback message the server returns; citations, filters
and record payloads are real outputs from the running API.

## 1. General DarGlobal question

**User:** What projects does DarGlobal showcase in Dubai?

- `query_type`: general
- `filters_applied`: `{city: Dubai}`
- `retrieved_count`: 7 (all `source=darglobal`)
- Sample citations: The Pagani Penthouse, W Residences, Urban Oasis by Missoni —
  each with its `darglobal.co.uk` source URL.

## 2. General Wasalt / exact constraints

**User:** Show me 3 bedroom apartments in Riyadh under 2 million SAR

- `filters_applied`: `{city: Riyadh, property_type: apartment, max_price: 2000000, bedrooms: 3}`
- Top citations:
  - Apartment with 3 Bedrooms — 850,000 SAR — Al-Mahdiyah, West Riyadh — `wasalt.sa/en/property/sale/apartment-with-3-bedrooms-5841667`
  - Apartment 101.3 SQM with 3 Bedrooms — 690,000 SAR — Al-Qadisiyah, East Riyadh
  - Apartment with 3 Bedrooms — 849,000 SAR
- All returned records satisfy `bedrooms == 3` and `price <= 2,000,000` (live test assertion).

## 3. Property-specific question

**User:** Tell me about Neptune by DarGlobal.

- Citation: Neptune, Interiors by Mouawad — Riyadh | Saudi Arabia — status
  "Under Development" — 5 bedrooms, area text "300 to 420" — archived snapshot
  with `snapshot_date` in metadata.
- `price` and `currency` are `null`; a grounded answer must say they are not
  listed rather than invent them.

## 4. Location-based search

**User:** Find apartments in Riyadh.

- Returns Wasalt Riyadh apartments with clickable listing URLs and price/bed/area
  cards; DarGlobal Riyadh development also appears when `source_filter=both`.

## 5. Cross-source comparison

**User:** Compare villas in Riyadh.

- Citations include a DarGlobal development (Neptune, no price) and several
  Wasalt villas (e.g. 1,300,000 SAR, 5 bed, Al-Hazm). A grounded comparison may
  only compare attributes present in the evidence; missing DarGlobal prices must
  be stated as unavailable.

## 6. Follow-up question

Client sends the `conversation_id` from the `done` event on the next request.
Server loads persisted history from `conversations`, supplies the last 8 turns as
context, and appends the new exchange. Example: "And the one in Al-Qadisiyah?"
resolves against previously retrieved records without treating the assistant's
own earlier wording as evidence.

## 7. Unsupported question

**User:** What is the population of Brazil?

```json
{
  "answer": "I don't have that information in the available DarGlobal/Wasalt data. I can help with projects, locations, property types, prices, and amenities that appear in the collected sources.",
  "citations": [],
  "warnings": ["no_retrieved_evidence"]
}
```
The LLM is never called on this path.

## 8. Unavailable pricing information

**User:** What is the price of the Pagani Penthouse in Dubai?

- Retrieval returns the DarGlobal record, but `price`/`currency` are `null`.
- Grounded behaviour: cite the project, state that no price is listed in the
  collected data, and note that the dataset reflects the last successful scrape.

## Freshness caveat

All answers must state that the information reflects the collection timestamp,
not real-time availability. DarGlobal data is explicitly archived.
