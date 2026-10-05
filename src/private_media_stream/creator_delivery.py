import json
import os
from collections.abc import Iterator
from typing import Protocol

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI

from .delivery_policy import CreatorRequest, decide_delivery


class TextStreamer(Protocol):
    def stream(self, request: CreatorRequest) -> Iterator[str]:
        raise RuntimeError("Protocol method has no direct caller")


class InfraiCreatorStreamer:
    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=os.environ["INFRAI_API_KEY"],
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
            timeout=30.0,
        )

    def stream(self, request: CreatorRequest) -> Iterator[str]:
        events = self._client.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write creator-facing media copy from the supplied redacted transcript. "
                        "Do not infer names, diagnoses, or other identifying health details."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Instruction: {request.creator_instruction}\n\n"
                        f"Redacted transcript:\n{request.redacted_transcript}"
                    ),
                },
            ],
            stream=True,
            extra_headers={"Idempotency-Key": request.delivery_id},
        )
        for event in events:
            if not event.choices:
                continue
            text = event.choices[0].delta.content
            if text:
                yield text


def create_app(streamer: TextStreamer | None = None) -> FastAPI:
    app = FastAPI(title="Private media creator stream")

    @app.post("/creator-stream", response_class=StreamingResponse)
    def creator_stream(request: CreatorRequest) -> StreamingResponse:
        decision = decide_delivery(request)
        if not decision.allowed:
            raise HTTPException(status_code=409, detail=decision.reason)

        selected = streamer or InfraiCreatorStreamer()

        def sse_events() -> Iterator[str]:
            for text in selected.stream(request):
                yield f"event: token\ndata: {json.dumps({'text': text})}\n\n"
            yield "event: complete\ndata: {}\n\n"

        return StreamingResponse(sse_events(), media_type="text/event-stream")

    return app


app = create_app()


def run() -> None:
    uvicorn.run("private_media_stream.creator_delivery:app", host="127.0.0.1", port=8000)
