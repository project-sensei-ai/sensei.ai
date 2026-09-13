"""
Channel abstraction — one shape for every place the agent is spoken to.

Teams, Slack and the web chat differ in transport, payload and consent model,
but the agent's side of the conversation is the same everywhere: a person said
something in a place, and the agent must decide whether it has anything useful
to add. Adapters translate; nothing above this line knows which channel it is.

Deliberately transport-free so it can be exercised without a Microsoft tenant,
a Slack workspace, or a public HTTPS endpoint.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol


class Channel(str, Enum):
    TEAMS = "teams"
    SLACK = "slack"
    WEB = "web"


@dataclass
class IncomingMessage:
    """Something a person said, normalised."""
    channel: Channel
    workspace_id: str
    conversation_id: str          # Teams channel id, Slack channel id, web session
    message_id: str
    text: str
    author_id: str                # platform user id
    author_name: str
    author_email: str | None = None
    mentioned_agent: bool = False
    is_reply: bool = False
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    """Something the agent decided to say."""
    text: str
    conversation_id: str
    reply_to_message_id: str | None = None
    citations: list[dict] = field(default_factory=list)


class ChannelAdapter(Protocol):
    """
    What every channel must provide.

    `parse` turns a platform payload into an IncomingMessage. `send` puts a
    reply back. `describe_grant` reports, in plain language, what this
    installation actually lets the agent read — the Trust page renders it, and
    it is written by the adapter because only the adapter knows the truth about
    its own consent model.
    """

    channel: Channel

    def parse(self, payload: dict, workspace_id: str) -> IncomingMessage | None:
        ...

    async def send(self, message: OutgoingMessage) -> None:
        ...

    def describe_grant(self, config: dict) -> dict:
        ...
