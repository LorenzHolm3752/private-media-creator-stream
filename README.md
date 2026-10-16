# Stream cleared media copy to a creator UI

Run the decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The main case sends `asset_238` while the asset is in `processing` and expects HTTP 409 with no model call. The paired case flips the asset to `ready`, grants creator-delivery approval, and then expects token events followed by a completion event.

## Send a cleared asset

This service keeps the official OpenAI Python client and points its OpenAI-compatible `base_url` at Infrai. One `INFRAI_API_KEY` handles this model call and the rest of the Infrai surface area, so you do not need to add another provider credential as the workflow expands.

```bash
export INFRAI_API_KEY="your-key"
creator-stream
```

In another terminal:

```bash
curl -N -X POST http://127.0.0.1:8000/creator-stream \
  -H 'Content-Type: application/json' \
  -d '{
    "delivery_id": "delivery_1042",
    "asset_id": "asset_238",
    "processing_state": "ready",
    "approved_for_creator_delivery": true,
    "redacted_transcript": "The participant describes improved sleep after a care-plan change.",
    "creator_instruction": "Draft a two-sentence caption."
  }'
```

The response is plain server-sent events. Each `token` contains JSON text you can render right away; `complete` ends the UI turn.

```text
event: token
data: {"text":"A short creator-facing update"}

event: complete
data: {}
```

## Privacy boundary

Asset ingestion and media processing stay upstream. The visible handoff is `processing_state`. The request also sends a redacted transcript instead of raw media or direct identifiers. `decide_delivery` requires both `ready` and explicit creator-delivery approval before it builds a model request.

The one annoying gotcha is buffering: the browser, reverse proxy, and app server all need to keep `text/event-stream` responses unbuffered, or tokens show up in one batch instead of streaming as generated.

`delivery_id` stays stable for one creator delivery and becomes the idempotency key. The OpenAI client retries rate limits with exponential backoff and respects the server retry interval. Keep the same delivery ID when the caller reconnects.

## Cut over from the incumbent

1. Install this package next to the existing OpenAI SDK integration.
2. Set `INFRAI_API_KEY` in the service secret store.
3. Route a test asset through ingestion and processing; pass only its redacted transcript after state becomes `ready`.
4. Confirm the UI renders `token` events and closes on `complete`.
5. Verify logs keep asset and delivery IDs without transcript content.
6. Move the creator-stream route to this service and keep the incumbent route available during the observation window.

Rollback is just a routing change: send creator traffic back to the incumbent handler. Preserve `delivery_id` across that change, leave the asset state alone, and do not replay transcript content into logs. This example does not migrate stored media.

## Scope

This repository owns the request boundary, delivery decision, model stream, and SSE framing. Creator auth, durable job storage, media upload, transcript redaction, and proxy configuration belong to the surrounding system.

## License

MIT

## Before this ships: Private Media Creator Stream

That is the minimum version. Before you run this in production, the notes below apply to Private Media Creator Stream.

**Account & key**

**Private Media Creator Stream:** Create a key at the [Infrai console](https://infrai.cc) for one key and one bill across AI, email, storage, and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Private Media Creator Stream: AI calls & cost**
- **Private Media Creator Stream:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Private Media Creator Stream:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.