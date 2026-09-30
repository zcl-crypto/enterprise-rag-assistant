from types import SimpleNamespace

import pytest

from rag_app.generation import GlmAnswerProvider, REFUSAL_TEXT, build_messages
from rag_app.vector_index import SearchHit


@pytest.mark.parametrize(
    ("model", "thinking_expected"),
    [("glm-4.7-flash", True), ("glm-4-flash-250414", False)],
)
def test_glm_adapter_uses_supported_parameters(monkeypatch, model: str, thinking_expected: bool) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", model)
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Policy answer [1]"))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=5),
        )

    monkeypatch.setattr(
        "openai.OpenAI",
        lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    provider = GlmAnswerProvider()
    source = SearchHit("chunk", "document", "version", "Policy text", (), None, 0.9)
    result = provider.answer("What is the policy?", [source])

    assert captured["model"] == model
    assert ("extra_body" in captured) is thinking_expected
    assert "每个事实后标注" in captured["messages"][0]["content"]
    assert result.text == "Policy answer [1]"
    assert (result.input_tokens, result.output_tokens) == (12, 5)


def test_refusal_retry_prompt_requires_complete_direct_evidence() -> None:
    source = SearchHit("chunk", "document", "version", "Policy text", (), None, 0.9)
    messages = build_messages("What is the policy?", [source], refusal_retry=True)
    assert "直接包含问题所需规则时必须回答" in messages[0]["content"]
    assert "不得补充常识" in messages[0]["content"]
    with pytest.raises(ValueError, match="Only one"):
        build_messages("What is the policy?", [source], citation_retry=True, refusal_retry=True)


@pytest.mark.parametrize(
    ("first_answer", "second_answer", "expected_calls", "expected_tokens"),
    [
        ("依据[1]，不允许。另一句没有引用。", "不允许。[1]", 2, (24, 10)),
        ("不允许。", "不允许。[1]", 2, (24, 10)),
        (REFUSAL_TEXT, REFUSAL_TEXT, 2, (24, 10)),
        (REFUSAL_TEXT, "Policy answer [1]", 2, (24, 10)),
    ],
)
def test_glm_retries_uncited_answers_and_refusals(
    monkeypatch, first_answer: str, second_answer: str | None,
    expected_calls: int, expected_tokens: tuple[int, int],
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    calls = []
    answers = [first_answer, second_answer]

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=answers[len(calls) - 1]))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=5),
        )

    monkeypatch.setattr(
        "openai.OpenAI",
        lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    provider = GlmAnswerProvider()
    source = SearchHit("chunk", "document", "version", "Policy text", (), None, 0.9)
    result = provider.answer("What is the policy?", [source])

    assert len(calls) == expected_calls
    if first_answer == REFUSAL_TEXT:
        assert "直接包含问题所需规则时必须回答" in calls[1]["messages"][0]["content"]
    elif expected_calls == 2:
        assert "每个包含事实的句子" in calls[1]["messages"][0]["content"]
    assert result.text == (second_answer if expected_calls == 2 else first_answer)
    assert (result.input_tokens, result.output_tokens) == expected_tokens
