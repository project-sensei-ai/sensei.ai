from strands import Agent, ModelRetryStrategy

from core.config import settings
from .tools import make_inventory_tool, make_search_tool, search_knowledge_base

SENSEI_SYSTEM_PROMPT = """You are Sensei, a permission-aware AI assistant embedded in a collaborative workspace.

You have access to a tool called `search_project_docs` that queries the workspace knowledge base — which contains indexed GitHub repositories, documentation, uploaded files, and other sources.

## Choosing a tool
Two different questions need two different tools:
- "What does the architecture say?" → `search_project_docs`. Searching passages.
- "Is there a doc about architecture?" / "what do you know about?" / "which
  sources do you have?" → `list_project_knowledge`. Reading the catalogue.

Asking search for a question about what exists will return passages from whatever
happens to discuss the topic, and miss a document whose title is the answer.

## Search budget
Search **once**. Search a second time only if the first result genuinely missed the
question, and a third only if that still left a real gap. Never repeat a search you
have already run with different wording — if two searches did not surface it, the
workspace does not contain it, and you should say so.

## When to use the tool
Call `search_project_docs` for ANY question that might be answered by workspace content:
- Questions about the project, codebase, architecture, or team
- Questions about commits, contributors, pull requests, or issues
- Questions about documentation, processes, or decisions recorded in the sources
- General "who / what / when / why" questions about the project

Do NOT call the tool for general programming questions, definitions, or topics clearly unrelated to this workspace.

## How to answer
- After searching, synthesise the retrieved passages into a clear, direct answer.
- Cite sources inline by their label: if a passage came from "my-repo", write
  [my-repo] after the claim. Never emit numeric or dagger markers such as
  【1†source】 or [1] — they render as noise and name nothing the reader can open.
- If no relevant content is found, say so honestly — do not fabricate project details.
- Keep answers concise; use markdown lists or code blocks where appropriate.
- If the question is entirely general knowledge (no workspace angle), answer directly without calling the tool.
"""


def _build_model():
    """
    The configured model, for any agent in the system.

    Shared so the chat agent and the background agents that write briefs cannot
    drift onto different backends — one LLM_BACKEND flag moves all of them.
    """
    if settings.LLM_BACKEND == "bedrock":
        import boto3
        from strands.models.bedrock import BedrockModel

        # Credentials in backend/.env are loaded by pydantic-settings, which does
        # not export them to the process environment — so boto3's default chain
        # cannot see them and Bedrock fails with NoCredentialsError even though
        # the keys are right there. Build the session explicitly instead. An IAM
        # role (no keys in .env) still works: boto3 falls back to its own chain.
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
        )
        # The session already carries the region; passing both is rejected.
        return BedrockModel(
            model_id=settings.BEDROCK_MODEL_ID,
            boto_session=session,
        )
    if settings.LLM_BACKEND == "ollama":
        from strands.models.openai import OpenAIModel
        return OpenAIModel(
            model_id=settings.OLLAMA_MODEL,
            client_args={"api_key": "ollama", "base_url": settings.OLLAMA_BASE_URL},
        )
    from strands.models.openai import OpenAIModel
    return OpenAIModel(
        model_id="openai/gpt-oss-120b",
        client_args={
            "api_key": settings.GROQ_API_KEY,
            "base_url": "https://api.groq.com/openai/v1",
        },
    )


def build_agent(workspace_id: str, chroma_client, session_manager=None):
    """
    Build a Strands Agent for the given workspace.
    Returns (agent, captured_citations_list).
    The citations list is populated in-place when the agent calls search_project_docs.
    Pass session_manager (e.g. S3SessionManager) to give the agent persistent conversation memory.
    """
    search_tool, captured = make_search_tool(workspace_id, chroma_client)
    model = _build_model()

    tools = [search_tool, make_inventory_tool(workspace_id, chroma_client)]
    if settings.BEDROCK_KB_ID:
        tools.append(search_knowledge_base)

    agent_kwargs = dict(
        model=model,
        tools=tools,
        system_prompt=SENSEI_SYSTEM_PROMPT,
        # The SDK default is 6 attempts backing off 4→8→16→32→64s, so a throttled
        # question sleeps for ~2 minutes before surfacing anything. On a free-tier
        # key that reads as a hang. Fail fast instead: ~14s worst case, then a
        # real error the user can act on.
        retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=8),
    )
    if session_manager is not None:
        agent_kwargs["session_manager"] = session_manager

    agent = Agent(**agent_kwargs)
    return agent, captured


def make_session_manager(session_id: str):
    """
    Return an S3SessionManager for the given session ID, or None if not configured.
    Used for agent conversation memory — the agent recalls prior turns in the same session.
    """
    if not settings.S3_SESSION_BUCKET:
        return None
    try:
        from strands.session.s3_session_manager import S3SessionManager
        return S3SessionManager(
            bucket_name=settings.S3_SESSION_BUCKET,
            session_id=session_id,
            region_name=settings.AWS_REGION,
        )
    except Exception:
        return None
