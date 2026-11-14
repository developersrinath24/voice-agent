"""Tests for the retrieval + generation chain.

No API keys are involved: a recording fake chat model stands in for DeepSeek so
we can assert on the prompt that would have been sent.
"""

from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.agents.clinic_assistant import ClinicAssistant
from app.rag.loaders import document_id
from app.rag.vector_store import add_documents
from app.services.prompts import NOT_FOUND_ANSWER
from tests.conftest import make_document


class RecordingChatModel(BaseChatModel):
    """Returns canned replies and keeps every prompt it was given."""

    responses: list[str] = Field(default_factory=lambda: ["The surgery closes at 18:30."])
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Sequence[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        self.seen.append(list(messages))
        text = self.responses[min(len(self.seen) - 1, len(self.responses) - 1)]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def _index(store, documents):
    add_documents(store, documents, [document_id(d) for d in documents])


def test_answer_is_built_from_retrieved_context(memory_store):
    _index(
        memory_store, [make_document("The surgery closes at 18:30 on weekdays.", "Opening hours")]
    )
    model = RecordingChatModel()

    answer = ClinicAssistant(model, store=memory_store, top_k=1, min_score=None).answer(
        "When does the surgery close?"
    )

    assert answer.text == "The surgery closes at 18:30."
    assert answer.grounded is True
    assert [source.section for source in answer.sources] == ["Opening hours"]

    system_message, human_message = model.seen[0][0], model.seen[0][-1]
    assert "Bramble Court Surgery" in system_message.content
    assert "CLINIC INFORMATION" in human_message.content
    assert "18:30" in human_message.content, "retrieved text must reach the prompt"
    assert "When does the surgery close?" in human_message.content


def test_no_relevant_context_skips_the_model_entirely(memory_store):
    model = RecordingChatModel()

    answer = ClinicAssistant(model, store=memory_store, top_k=3, min_score=None).answer(
        "Do you offer physiotherapy?"
    )

    assert answer.grounded is False
    assert answer.text == NOT_FOUND_ANSWER
    assert answer.sources == []
    assert model.seen == [], "a grounding gate that still calls the model is not a gate"


def test_history_is_sent_as_conversation_turns(memory_store):
    _index(memory_store, [make_document("Saturday hours are 09:00 to 12:00.", "Opening hours")])
    model = RecordingChatModel()

    ClinicAssistant(model, store=memory_store, top_k=1, min_score=None).answer(
        "And on Saturday?",
        history=[
            ("user", "When are you open?"),
            ("assistant", "Monday to Friday, 08:00 to 18:30."),
        ],
    )

    roles = [message.type for message in model.seen[0]]
    assert roles == ["system", "human", "ai", "human"]


def test_missing_answer_is_short_circuited_not_paraphrased(memory_store):
    _index(memory_store, [make_document("The surgery closes at 18:30.", "Opening hours")])
    model = RecordingChatModel(responses=["I am not sure."])

    answer = ClinicAssistant(model, store=memory_store, top_k=1, min_score=0.99).answer(
        "What are your car park charges for coaches?"
    )

    assert answer.grounded is False
    assert model.seen == []
