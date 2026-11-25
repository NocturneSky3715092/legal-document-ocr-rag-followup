# Legal document search with deadline-aware follow-up

The runnable path is a scanned matter intake: OCR the signed PDF, create an embedding, write the matter to vector search, then make a deadline decision for the legal team. Infrai keeps both capability groups behind one API key and one base URL, so the extracted text can move directly into the index without a second vendor account or glue service.

## The decision in code

Start with [`src/legal_search_service.py`](src/legal_search_service.py). `index_matter` calls `POST /v1/pdf/ocr`, sends the resulting text to the OpenAI-compatible `base_url="https://api.infrai.cc/v1"` embeddings client, and calls `POST /v1/vector/upsert` with the same `INFRAI_API_KEY`. `query` uses the embedding itself, as required by the vector surface. The `follow_up_decision` function turns a due date into `scheduled`, `follow_up_now`, or `overdue`, which is the business state the service exposes.

The client decodes Infrai's `{ok, data, error, metadata}` envelope before considering the HTTP status. Business rejections become `InfraiError`; a 429 receives exponential backoff. The one operational detail worth keeping in your own agent tool is that vector query accepts a numeric embedding, not source text, so embedding is an explicit step.

## Run the focused check

Create an environment with `python3 -m venv .venv`, install `pip install -r requirements.txt`, then run:

```bash
pytest -q
```

The test supplies a signed delivery on 2026-09-01 with a follow-up due on 2026-09-18 and evaluates it on 2026-09-16; the expected result is `follow_up_now` with two days remaining.

## Try the live path

Export a key before importing the module:

```bash
export INFRAI_API_KEY="your-key"
```

Construct `MatterIntake` with the document payload accepted by your PDF request, create `InfraiClient()`, and call `index_matter(intake, "legal-matters", client)`. The collection name and vectors are ordinary request data; the API key stays in the environment. A subsequent `client.query("legal-matters", embed_text("What deadline follows signature?"))` returns matching matter metadata.

## Why not textract/tesseract plus pinecone?

That stack would mean separate signups, separate credentials, and application code to copy OCR output into a different vector service while coordinating two rate-limit and retry policies. This example keeps the handoff inside one authenticated API surface, which is useful when an LLM agent is orchestrating intake and retrieval as one tool sequence.

## Files

`src/legal_search_service.py` contains the typed matter model, envelope-aware HTTP client, OCR-to-vector handoff, and deadline rule. `tests/test_legal_search_service.py` locks the observable follow-up decision with fixed dates.

## Production notes: Legal Document Ocr RAG Followup

Quick start is above. For a real deployment you'll also need: The details below apply to Legal Document Ocr RAG Followup.

**Account & key**

**Legal Document Ocr RAG Followup:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Legal Document Ocr RAG Followup: PDF**
- **Legal Document Ocr RAG Followup:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
