from typing import Annotated, Any, List, TypedDict

try:
    from langchain_core.messages import BaseMessage
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    BaseMessage = Any

try:
    from langgraph.graph.message import add_messages
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    def add_messages(current, new):
        return (current or []) + (new or [])

try:
    from langchain.agents import AgentState as LangChainAgentState
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    class LangChainAgentState(TypedDict):
        messages: Annotated[List[BaseMessage], add_messages]


class MetaKeys:
    """Metadata keys used by the centralized EpiAgent runtime."""

    AWAITING_USER_CLARIFICATION = "awaiting_user_clarification"
    LAST_USER_MESSAGE_HASH = "last_user_message_hash"
    THREAD_ID = "thread_id"
    NEXT_EVENT_SEQ = "next_event_seq"
