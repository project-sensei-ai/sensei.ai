from strands import Agent

from core.config import settings
from .tools import make_search_tool

SENSEI_SYSTEM_PROMPT = """You are Sensei, a permission-aware AI assistant embedded in a collaborative workspace.

You have access to a tool called `search_project_docs` that queries the workspace knowledge base — which contains indexed GitHub repositories, documentation, uploaded files, and other sources.

## When to use the tool
Call `search_project_docs` for ANY question that might be answered by workspace content:
- Questions about the project, codebase, architecture, or team
- Questions about commits, contributors, pull requests, or issues
- Questions about documentation, processes, or decisions recorded in the sources
- General "who / what / when / why" questions about the project

Do NOT call the tool for general programming questions, definitions, or topics clearly unrelated to this workspace.

## How to answer
- After searching, synthesise the retrieved passages into a clear, direct answer.
- Cite sources inline: if a passage came from "my-repo", write [my-repo] after the claim.
- If no relevant content is found, say so honestly — do not fabricate project details.
- Keep answers concise; use markdown lists or code blocks where appropriate.
- If the question is entirely general knowledge (no workspace angle), answer directly without calling the tool.
"""


def build_agent(workspace_id: str, chroma_client, session_manager=None):
    """
    Build a Strands Agent for the given workspace.
    Returns (agent, captured_citations_list).
    The citations list is populated in-place when the agent calls search_project_docs.
    Pass session_manager (e.g. S3SessionManager) to give the agent persistent conversation memory.
    """
    search_tool, captured = make_search_tool(workspace_id, chroma_client)

    if settings.LLM_BACKEND == "bedrock":
        from strands.models.bedrock import BedrockModel
        model = BedrockModel(
            model_id=settings.BEDROCK_MODEL_ID,
            region_name=settings.AWS_REGION,
        )
    else:
        from strands.models.openai import OpenAIModel
        model = OpenAIModel(
            model_id="openai/gpt-oss-120b",
            client_args={
                "api_key": settings.GROQ_API_KEY,
                "base_url": "https://api.groq.com/openai/v1",
            },
        )

    agent_kwargs = dict(
        model=model,
        tools=[search_tool],
        system_prompt=SENSEI_SYSTEM_PROMPT,
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
