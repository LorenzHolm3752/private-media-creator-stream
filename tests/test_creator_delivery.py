from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from private_media_stream.creator_delivery import InfraiCreatorStreamer, create_app
from private_media_stream.delivery_policy import CreatorRequest


class RecordingStreamer:
    def __init__(self) -> None:
        self.delivered_assets: list[str] = []

    def stream(self, request: CreatorRequest) -> Iterator[str]:
        self.delivered_assets.append(request.asset_id)
        yield "A calm "
        yield "creator update."


def request_body(*, ready: bool, approved: bool) -> dict[str, object]:
    return {
        "delivery_id": "delivery_1042",
        "asset_id": "asset_238",
        "processing_state": "ready" if ready else "processing",
        "approved_for_creator_delivery": approved,
        "redacted_transcript": "The participant describes improved sleep after a care-plan change.",
        "creator_instruction": "Draft a two-sentence caption.",
    }


def test_ready_approved_asset_streams_to_creator() -> None:
    streamer = RecordingStreamer()
    client = TestClient(create_app(streamer))

    response = client.post("/creator-stream", json=request_body(ready=True, approved=True))

    assert response.status_code == 200
    assert streamer.delivered_assets == ["asset_238"]
    assert 'data: {"text": "A calm "}' in response.text
    assert "event: complete" in response.text


def test_unfinished_asset_never_reaches_model_stream() -> None:
    streamer = RecordingStreamer()
    client = TestClient(create_app(streamer))

    response = client.post("/creator-stream", json=request_body(ready=False, approved=True))

    assert response.status_code == 409
    assert response.json() == {"detail": "Asset processing is not complete"}
    assert streamer.delivered_assets == []


def test_choice_less_stream_chunks_do_not_interrupt_tokens(monkeypatch) -> None:
    client = Mock()
    client.chat.completions.create.return_value = iter(
        [
            SimpleNamespace(choices=[]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))]),
            SimpleNamespace(choices=[]),
        ]
    )
    monkeypatch.setattr("private_media_stream.creator_delivery.OpenAI", lambda **kwargs: client)

    assert list(InfraiCreatorStreamer().stream(CreatorRequest(**request_body(ready=True, approved=True)))) == ["Hello"]
