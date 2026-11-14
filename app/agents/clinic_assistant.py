"""The clinic assistant: retrieval plus generation.

The chain is deliberately short — retrieve, ground, answer — because every step
has to be explainable:

    question
      -> Qdrant similarity search (top_k, with a relevance floor)
      -> numbered context block
      -> system prompt + conversation history + context
      -> DeepSeek (Gemini on failure)
      -> plain text answer

If nothing clears the relevance floor we do not call the model at all. A grounded
"call reception" beats a fluent invention, and it costs nothing.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_qdrant import QdrantVectorStore

from app.core.config import settings
from app.rag import retriever
from app.rag.retriever import RetrievedChunk, format_context
from app.services.prompts import NOT_FOUND_ANSWER, SYSTEM_PROMPT, USER_TEMPLATE

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("history", optional=True),
        ("human", USER_TEMPLATE),
    ]
)


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[RetrievedChunk] = field(default_factory=list)
    grounded: bool = True


def _to_messages(history: Sequence[tuple[str, str]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for role, content in history:
        messages.append(HumanMessage(content) if role == "user" else AIMessage(content))
    return messages


class ClinicAssistant:
    def __init__(
        self,
        llm: Runnable,
        *,
        store: QdrantVectorStore | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> None:
        self.llm = llm
        self.store = store
        self.top_k = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
        self.min_score = min_score if min_score is not None else settings.RETRIEVAL_MIN_SCORE
        self.chain = PROMPT | self.llm | StrOutputParser()

    def answer(self, question: str, history: Sequence[tuple[str, str]] = ()) -> Answer:
        chunks = retriever.retrieve(
            question,
            top_k=self.top_k,
            store=self.store,
            min_score=self.min_score,
        )

        # Grounding gate: no relevant passage, no model call.
        if not chunks:
            return Answer(text=NOT_FOUND_ANSWER, sources=[], grounded=False)

        text = self.chain.invoke(
            {
                "context": format_context(chunks),
                "question": question,
                "history": _to_messages(history),
            }
        )
        return Answer(text=text.strip(), sources=chunks, grounded=True)
