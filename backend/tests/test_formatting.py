"""plain_answer: model output as a person would type it in a chat message."""
from core.formatting import plain_answer


def test_empty_and_none():
    assert plain_answer(None) == ""
    assert plain_answer("") == ""
    assert plain_answer("   \n\n ") == ""


def test_plain_text_is_untouched():
    text = "The production deploy window is Tuesday to Thursday, 10:00 to 16:00 IST."
    assert plain_answer(text) == text


def test_lenticular_markers_removed_bold_kept():
    assert plain_answer("**Priya Nair**【1】") == "**Priya Nair**"
    assert plain_answer("On call is **Priya Nair**【1†source】.") == "On call is **Priya Nair**."
    assert plain_answer("Release captain is Daniel【3:0†runbook.md】 this week.") == \
        "Release captain is Daniel this week."


def test_numeric_reference_markers_removed():
    assert plain_answer("Deploys run on Tuesdays [1].") == "Deploys run on Tuesdays."
    assert plain_answer("Deploys run on Tuesdays[2][3].") == "Deploys run on Tuesdays."
    assert plain_answer("See the runbook [1, 2] for details.") == "See the runbook for details."
    assert plain_answer("A footnote[^1] here.") == "A footnote here."
    assert plain_answer("A footnote [^note] here.") == "A footnote here."


def test_bracketed_source_labels_removed():
    assert plain_answer("[Confluence: SD › Apollo — Deployment runbook]") == ""
    assert plain_answer("The window is 10:00–16:00 [Confluence: SD › Apollo — Deployment runbook].") == \
        "The window is 10:00–16:00."
    assert plain_answer("It lives in the service [bsaisuryacharan/apollo-delivery-service].") == \
        "It lives in the service."
    assert plain_answer("Configured in [deploy/config.yaml] today.") == "Configured in today."
    assert plain_answer("Status is In Progress [Jira KAN-12 live].") == "Status is In Progress."
    assert plain_answer("Discussed in [Slack #all-sensei].") == "Discussed in."
    assert plain_answer("From [GitHub: apollo-delivery-service] README.") == "From README."
    assert plain_answer("[Source: Apollo on-call rota] Priya is on call.") == "Priya is on call."


def test_source_trailers_removed():
    text = "The window is Tuesday to Thursday.\n\n*(Source: [Confluence: SD › Apollo — Deployment runbook])*"
    assert plain_answer(text) == "The window is Tuesday to Thursday."
    assert plain_answer("Priya is on call (Source: on-call rota).") == "Priya is on call."
    assert plain_answer("Priya is on call.\nSource: Confluence on-call rota") == "Priya is on call."
    assert plain_answer("Priya is on call.\n\n**Sources:**\n- [Confluence: SD › Rota]\n- [Jira KAN-3]") == \
        "Priya is on call."


def test_markdown_links_become_text():
    assert plain_answer("Read the [deployment runbook](https://example.atlassian.net/wiki/x) first.") == \
        "Read the deployment runbook first."


def test_headings_become_bold_lines():
    assert plain_answer("## On call\nPriya Nair") == "**On call**\nPriya Nair"
    assert plain_answer("### **Release captain** ###") == "**Release captain**"


def test_tables_become_bullets():
    table = (
        "| Role | Person |\n"
        "|------|--------|\n"
        "| On call | **Priya Nair** 【1】 |\n"
        "| Release captain | Daniel Okafor |\n"
    )
    assert plain_answer(table) == "- Role — Person\n- On call — **Priya Nair**\n- Release captain — Daniel Okafor"
    aligned = "| a | b |\n|:---|---:|\n| 1 | 2 |"
    assert plain_answer(aligned) == "- a — b\n- 1 — 2"


def test_horizontal_rules_dropped():
    assert plain_answer("First.\n\n---\n\nSecond.") == "First.\n\nSecond."
    assert plain_answer("First.\n***\nSecond.") == "First.\nSecond."


def test_italics_markers_dropped_bold_kept():
    assert plain_answer("This is *really* important and **Tuesday** is the day.") == \
        "This is really important and **Tuesday** is the day."
    assert plain_answer("An _italic_ word.") == "An italic word."
    assert plain_answer("snake_case_name stays") == "snake_case_name stays"
    assert plain_answer("2 * 3 * 4 = 24") == "2 * 3 * 4 = 24"


def test_bullets_normalised_and_kept():
    assert plain_answer("* one\n* two\n* three") == "- one\n- two\n- three"
    assert plain_answer("- one\n- two") == "- one\n- two"
    assert plain_answer("• one\n• two") == "- one\n- two"
    assert plain_answer("1. first\n2. second") == "1. first\n2. second"


def test_blank_lines_collapsed():
    assert plain_answer("One.\n\n\n\n\nTwo.") == "One.\n\nTwo."


def test_keeps_numbers_times_currency_and_ticket_keys():
    text = "KAN-12 ships at 14:30 IST on 16 Sept, costs $1,200 (about ₹99,800), and 3.5% of traffic."
    assert plain_answer(text) == text


def test_inline_code_kept_with_its_backticks():
    assert plain_answer("Use `items[0]` to read the first order.") == "Use `items[0]` to read the first order."
    assert plain_answer("Call `deploy --env [prod]` then wait.") == "Call `deploy --env [prod]` then wait."


def test_code_like_indexing_outside_backticks_kept():
    assert plain_answer("items[0].name is the order id.") == "items[0].name is the order id."
    assert plain_answer("grid[1][2] = 7 sets it.") == "grid[1][2] = 7 sets it."
    assert plain_answer("Call handlers[0](event) first.") == "Call handlers[0](event) first."


def test_fenced_code_kept_verbatim_with_its_fences():
    text = "Run this:\n```bash\nkubectl rollout undo deploy/api [1]\n```\nThen check."
    assert plain_answer(text) == text
    tilde = "~~~\nfoo[1]\n# a comment\n---\n~~~"
    assert plain_answer(tilde) == tilde


def test_ordinary_brackets_kept():
    assert plain_answer("Choose [yes] or [no].") == "Choose [yes] or [no]."


def test_realistic_messy_answer():
    messy = (
        "### Who is on call\n\n"
        "The on-call engineer for the week of **15 September** is **Priya Nair**【1】, and the release "
        "captain is Daniel Okafor [Confluence: SD › Apollo — On-call rota].\n\n"
        "---\n\n"
        "| Role | Person |\n|---|---|\n| On call | Priya Nair |\n\n"
        "*(Source: [Confluence: SD › Apollo — Deployment runbook])*"
    )
    assert plain_answer(messy) == (
        "**Who is on call**\n\n"
        "The on-call engineer for the week of **15 September** is **Priya Nair**, and the release "
        "captain is Daniel Okafor.\n\n"
        "- Role — Person\n- On call — Priya Nair"
    )


def test_idempotent():
    messy = "## Title\n**Priya Nair**【1】 [Confluence: SD › Rota]\n| a | b |\n|---|---|\n| 1 | 2 |"
    once = plain_answer(messy)
    assert plain_answer(once) == once


# Review fixes: idempotence, source lines with content, source blocks, links, prose brackets.

CODE_BEARING = [
    "Use `arr[1]` to read it.",
    "```python\nprint(x[1])\n```",
    "Run `grep '[0-9]' file`",
    "Run this:\n```bash\n# install deps\nnpm run build -- --mode prod\n```\nCall `foo()` then pass `**kwargs` and **Priya** owns it.",
    "~~~\nfoo[1]\n\nbar[2]\n~~~",
    "Call handlers[0](event) first.",
    "## Title\n**Priya Nair**【1】 [Confluence: SD › Rota]\n| a | b |\n|---|---|\n| 1 | 2 |",
    "Priya is on call.\n\nSources:\n- Deployment runbook (Confluence)\n- KAN-12",
    "**References:** KAN-12 and KAN-14 block the release.",
]


def test_idempotent_for_code_bearing_answers():
    for text in CODE_BEARING:
        once = plain_answer(text)
        assert plain_answer(once) == once, text


def test_code_survives_a_second_pass():
    assert plain_answer(plain_answer("Use `arr[1]` to read it.")) == "Use `arr[1]` to read it."
    assert plain_answer(plain_answer("```python\nprint(x[1])\n```")) == "```python\nprint(x[1])\n```"
    assert plain_answer(plain_answer("Run `grep '[0-9]' file`")) == "Run `grep '[0-9]' file`"


def test_source_prefix_with_content_keeps_the_content():
    assert plain_answer("**References:** KAN-12 and KAN-14 block the release.") == \
        "KAN-12 and KAN-14 block the release."
    assert plain_answer("Reference: the deploy window is 10:00–16:00 IST.") == \
        "the deploy window is 10:00–16:00 IST."


def test_sources_block_removed_with_its_list():
    assert plain_answer("Priya is on call.\n\nSources:\n- Deployment runbook (Confluence)\n- KAN-12") == \
        "Priya is on call."
    assert plain_answer("Priya is on call.\n\nSources:\n\n1. Runbook\n2. Rota\n\nAsk her first.") == \
        "Priya is on call.\n\nAsk her first."


def test_links_with_relative_or_bare_targets_become_text():
    assert plain_answer("See the [Upload guide](docs/upload.md) first.") == "See the Upload guide first."
    assert plain_answer("Open the [Jira board](jira.example.com/browse/KAN) now.") == "Open the Jira board now."


def test_prose_and_code_brackets_kept():
    assert plain_answer("Built with [Next.js] and [Doc review pending] status.") == \
        "Built with [Next.js] and [Doc review pending] status."
    assert plain_answer("Pick severity [1-4] when filing.") == "Pick severity [1-4] when filing."
    assert plain_answer("Digits match [0-9]+ here.") == "Digits match [0-9]+ here."
    assert plain_answer("Use arr[1] to get the second item.") == "Use arr[1] to get the second item."
    assert plain_answer("Choose [yes/no] now.") == "Choose [yes/no] now."
    assert plain_answer("Deploys run Tuesday. [1-2]") == "Deploys run Tuesday."


def test_bold_italic_triple_markers_become_bold():
    assert plain_answer("The window is ***Friday 6pm***.") == "The window is **Friday 6pm**."
    assert plain_answer("The window is ___Friday 6pm___.") == "The window is **Friday 6pm**."


def test_call_parentheses_outside_code_kept():
    assert plain_answer("Call foo() first.") == "Call foo() first."
