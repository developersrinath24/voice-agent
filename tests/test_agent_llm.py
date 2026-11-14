import json

import pytest

from app.api.routes.llm import BUFFER_PHRASE, FAILURE_ANSWER
from app.core.config import settings

SECRET = "agent-secret-for-tests"
AUTH = {"Authorization": f"Bearer {SECRET}"}


@pytest.fixture(autouse=True)
def agent_secret(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_LLM_SECRET", SECRET)


def ask(client, messages=None, headers=AUTH):
    return client.post(
        "/v1/chat/completions",
        json={"messages": messages or []},
        headers=headers,
    )


def events(response):
    """Split an SSE body into the text chunks and check the terminator."""
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    payloads = [json.loads(line[len("data: ") :]) for line in lines[:-1]]
    return payloads


def spoken(payloads) -> str:
    return "".join(payload["choices"][0]["delta"].get("content", "") for payload in payloads)


def test_answers_a_turn_as_server_sent_events(client, fake_assistant):
    response = ask(client, [{"role": "user", "content": "When do you close on Tuesday?"}])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    payloads = events(response)
    text = spoken(payloads)

    # Buffer first: the caller hears something while retrieval runs.
    assert payloads[0]["choices"][0]["delta"]["content"] == BUFFER_PHRASE
    assert text == BUFFER_PHRASE + fake_assistant.text
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"
    assert fake_assistant.calls[0][0] == "When do you close on Tuesday?"


def test_history_comes_from_the_messages_before_the_question(client, fake_assistant):
    messages = [
        {"role": "system", "content": "You are reception."},
        {"role": "user", "content": "What time do you close?"},
        {"role": "assistant", "content": "We close at 18:30."},
        {"role": "user", "content": "And on Saturday?"},
    ]
    assert ask(client, messages).status_code == 200

    question, history = fake_assistant.calls[0]
    assert question == "And on Saturday?"
    assert history == [
        ("user", "What time do you close?"),
        ("assistant", "We close at 18:30."),
    ]


def test_only_the_last_user_message_is_the_question(client, fake_assistant):
    messages = [
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second"},
    ]
    ask(client, messages)
    assert fake_assistant.calls[0][0] == "second"


def test_content_parts_are_flattened(client, fake_assistant):
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Do you take walk-ins?"}],
        }
    ]
    ask(client, messages)
    assert fake_assistant.calls[0][0] == "Do you take walk-ins?"


def test_a_broken_turn_is_spoken_not_raised(client, fake_assistant, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("vector store is down")

    monkeypatch.setattr(fake_assistant, "answer", explode)

    response = ask(client, [{"role": "user", "content": "hello"}])
    assert response.status_code == 200

    payloads = events(response)
    assert spoken(payloads) == BUFFER_PHRASE + FAILURE_ANSWER
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"


def test_a_missing_secret_disables_the_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "AGENT_LLM_SECRET", "")
    assert ask(client).status_code == 503


def test_wrong_or_absent_secret_is_rejected(client, fake_assistant):
    question = [{"role": "user", "content": "hello"}]
    assert ask(client, question, headers={}).status_code == 401
    assert ask(client, question, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert ask(client, question, headers={"xi-api-key": SECRET}).status_code == 200
    assert ask(client, question, headers={"x-api-key": SECRET}).status_code == 200


def test_the_endpoint_ignores_the_user_facing_api_key(client, monkeypatch):
    # Even with API_KEY set, the agent endpoint authenticates with its own
    # secret; ElevenLabs is never given the browser-facing key.
    monkeypatch.setattr(settings, "API_KEY", "shared-secret")
    assert ask(client, [{"role": "user", "content": "hello"}]).status_code == 200


def test_a_request_without_a_user_message_is_refused(client):
    response = ask(client, [{"role": "system", "content": "hi"}])
    assert response.status_code == 422
