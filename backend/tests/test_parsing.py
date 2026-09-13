"""Parsers that turned out to matter more than they look."""
from agent.gaps import _parse_draft
from sources.routes import ConfluenceSourceIn


def _conf(url: str) -> str:
    return ConfluenceSourceIn(
        type="confluence", base_url=url, email="a@b.com",
        api_token="x", space_key="ENG",
    ).base_url


def test_a_pasted_page_url_is_trimmed_to_the_site():
    """People paste the page they are looking at. Twice, in this project."""
    assert _conf(
        "https://charanb.atlassian.net/wiki/spaces/~7120/pages/393218/Architcture+doc"
    ) == "https://charanb.atlassian.net/wiki"


def test_a_bare_site_url_is_left_alone():
    assert _conf("https://charanb.atlassian.net/wiki") == "https://charanb.atlassian.net/wiki"
    assert _conf("https://charanb.atlassian.net/wiki/") == "https://charanb.atlassian.net/wiki"


def test_a_name_is_rejected_with_a_usable_message():
    try:
        _conf("sai charan")
        assert False, "should have raised"
    except ValueError as exc:
        assert "address bar" in str(exc)


def test_draft_title_ignores_shell_output_in_code_fences():
    """
    Regression: a deployment guide's first '#' line was inside a fenced block of
    docker output, and one draft ended up titled
    "backend   | 0.0.0.0:8000->8000/tcp".
    """
    text = (
        "**Deployment Guide**\n\nBuild it.\n\n"
        "```\ndocker compose ps\n# backend   | 0.0.0.0:8000->8000/tcp\n```\n\n"
        "## Sources\n- Dockerfile\n\n## Assumptions\n- registry is ECR\n"
    )
    draft = _parse_draft(text, "Deployment guide")
    assert draft.title == "Deployment Guide"
    assert draft.sources_used == ["Dockerfile"]
    assert draft.assumptions == ["registry is ECR"]
    assert "## Sources" not in draft.body_markdown


def test_draft_falls_back_to_the_gap_title():
    draft = _parse_draft("just prose, no heading\n", "Local run guide")
    assert draft.title == "Local run guide"


def test_none_assumptions_are_not_listed_as_an_assumption():
    draft = _parse_draft("# X\n\nbody\n\n## Assumptions\n- None\n", "X")
    assert draft.assumptions == []
