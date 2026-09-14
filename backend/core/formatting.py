"""
Answers read as plain sentences.

The prompt asks for plain text, and most turns comply. Some models still reach
for citation markers (【1】, [2], [Confluence: SD › Runbook]), tables and
headings, and a chat bubble that renders text as text shows every one of them
as a stray symbol. `plain_answer` is the net under the prompt: it keeps what
reads well in a message (**bold**, "- " bullets, numbers, ticket keys, inline
`code` and fenced code blocks, both verbatim) and removes the rest. Sources are
shown under the answer anyway, so a bracketed label in the prose adds nothing.

It is idempotent: code keeps its backticks and fences, so running it again (the
client does, over stored messages) changes nothing.
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_RULE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$")
_SOURCE_LINE = re.compile(
    r"^(\s*)[*_>]*\s*\(?\s*[*_]*\s*(?:sources?|references?|citations?)\s*[*_]*\s*:\s*[*_]*\s*(.*)$", re.I)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+•●▪◦]|\d+[.)])\s+")
_SOURCE_PAREN = re.compile(r"\s*[*_]*\(\s*(?:sources?|per|see)\s*:[^()\n]*\)[*_]*", re.I)
_LENTICULAR = re.compile(r"【[^】\n]*】")
_LINK = re.compile(r"(?<![\w\]])\[([^\[\]\n]+)\]\((?:[^()\s]|\([^()\s]*\))+\)")
_BRACKET = re.compile(r"\[([^\[\]\n]{1,200})\]")
_CODE = re.compile(r"`([^`\n]+)`")
_BULLET = re.compile(r"^(\s*)(?:[*•●▪◦]|\+)\s+")
_TRIPLE_STAR = re.compile(r"\*{3}(?=\S)([^*\n]+?)(?<=\S)\*{3}")
_TRIPLE_UNDER = re.compile(r"_{3}(?=\S)([^_\n]+?)(?<=\S)_{3}")
_ITALIC_STAR = re.compile(r"(?<![*\w])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?![*\w])")
_ITALIC_UNDER = re.compile(r"(?<![\w_])_(?![\s_])([^_\n]+?)(?<![\s_])_(?![\w_])")

# A bracket is a source label only in the shapes sources are actually named:
# "Word: ...", "... › ...", "Jira KAN-12", "Slack #channel", owner/repo, a doc path.
_LABEL_COLON = re.compile(
    r"^\s*(?:source|sources|confluence|jira|slack|github|gitlab|repo|meeting|file|doc|document|"
    r"upload|url|web|wiki|team answers?)\s*:",
    re.I,
)
_CONNECTOR = re.compile(r"^\s*(?:jira\s+[A-Za-z][A-Za-z0-9]+-\d+\b|slack\s+#[\w-]+)", re.I)
_REPO_SLUG = re.compile(r"^[\w.-]{2,}/[\w.-]{2,}(?:/[\w./-]*)?$")
_FILE_PATH = re.compile(r"^[\w./-]+\.[A-Za-z]{1,5}$")
_DOC_EXT = re.compile(r"\.(?:md|pdf|docx?|txt|ya?ml|json|csv|xlsx?|pptx?|html?)$", re.I)


def _is_source_label(inner: str) -> bool:
    s = inner.strip()
    if not s:
        return False
    if "›" in s or "†" in s or _LABEL_COLON.match(s) or _CONNECTOR.match(s):
        return True
    if _REPO_SLUG.match(s) and re.search(r"[-_.\d]", s):
        return True
    return bool(_FILE_PATH.match(s) and ("/" in s or _DOC_EXT.search(s)))


_REF_CHAIN = re.compile(r"(?:\[(?:\^?\d+(?:\s*[,–-]\s*\^?\d+)*|\^[\w-]+|\d+(?::\d+)?†[^\]\n]*)\])+")
_RANGE = re.compile(r"^\[\d+\s*[–-]\s*\d+\]$")


def _clean_brackets(line: str) -> str:
    def chain(m: re.Match) -> str:
        start, end = m.start(), m.end()
        text = m.group(0)
        before = line[start - 1] if start > 0 else ""
        rest = line[end:]
        if "†" in text or "^" in text:
            return ""
        if re.match(r"[+*?{]", rest):
            return text                                     # [0-9]+ is a pattern
        if before.isalnum() or before in "_)]":
            # arr[1] to read it, items[0].name, grid[1][2] = 7 are code; only a
            # marker glued to the end of a sentence ("Tuesdays[2][3].") is a citation.
            return "" if re.match(r"[.,;:!?]?\s*$|[.,;:!?](?=\s)", rest) else text
        if _RANGE.match(text):
            # "severity [1-4]" is prose; a range standing after a sentence is a citation.
            return "" if re.search(r"[.!?]\s*$", line[:start]) else text
        return ""

    line = _REF_CHAIN.sub(chain, line)

    def label(m: re.Match) -> str:
        return "" if _is_source_label(m.group(1)) else m.group(0)

    return _BRACKET.sub(label, line)


def _table_row(line: str) -> str | None:
    s = line.strip()
    if not (s.startswith("|") and s.count("|") >= 2):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")]
    cells = [c for c in cells if c]
    if not cells:
        return ""
    return "- " + " — ".join(cells)


def _inline(line: str) -> str:
    # Inline code is shielded from every rule below and comes back with its backticks.
    shelf: list[str] = []

    def keep(m: re.Match) -> str:
        shelf.append(m.group(1))
        return f"\x00{len(shelf) - 1}\x00"

    line = _CODE.sub(keep, line)
    line = _LENTICULAR.sub("", line)
    line = _SOURCE_PAREN.sub("", line)
    line = _LINK.sub(r"\1", line)
    line = _clean_brackets(line)
    line = _TRIPLE_STAR.sub(r"**\1**", line)
    line = _TRIPLE_UNDER.sub(r"**\1**", line)
    line = _ITALIC_STAR.sub(r"\1", line)
    line = _ITALIC_UNDER.sub(r"\1", line)
    line = re.sub(r"\*\*\s*\*\*", "", line)                 # bold wrapped around nothing
    line = re.sub(r"(\*\*[^*\n]*?)\s+\*\*(?=[\s.,;:!?]|$)", r"\1**", line)  # "**Priya **" -> "**Priya**"
    line = re.sub(r"[ \t]+([.,;:!?])(?=\s|$)", r"\1", line)  # space left before punctuation
    line = re.sub(r"(?<=\S)[ \t]{2,}", " ", line)
    line = re.sub(r"(?<![\w)\]])\(\s*\)", "", line)          # parentheses emptied by the clean-up
    return re.sub(r"\x00(\d+)\x00", lambda m: f"`{shelf[int(m.group(1))]}`", line).rstrip()


def _is_empty_label(rest: str) -> bool:
    """What follows 'Sources:' is only labels and markers, nothing a person would miss."""
    return not re.sub(r"[\s*_()\[\],;.:—–-]", "", _inline(rest))


# Some models write their private reasoning into the answer itself, closed by a
# </think> tag (the opening tag is often in the prompt template, not the text).
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.S | re.I)
_THINK_OPEN = re.compile(r"<think>.*\Z", re.S | re.I)

# Typographic look-alikes a model uses in IDs and numbers. CHG\u20115518 with a
# non-breaking hyphen does not match CHG-5518 in Jira search or Ctrl+F.
_LOOKALIKES = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2212": "-",
    "\u00a0": " ", "\u202f": " ", "\u2007": " ", "\u2009": " ", "\u200a": " ",
    "\u200b": "", "\u2060": "", "\ufeff": "",
})


def without_reasoning(text: str | None) -> str:
    """The text a model meant to say, with any leaked reasoning block removed."""
    if not text:
        return ""
    close = list(re.finditer(r"</think>", text, re.I))
    if close and not re.search(r"<think>", text[:close[-1].start()], re.I):
        text = text[close[-1].end():]                       # "reasoning...</think> answer"
    text = _THINK_BLOCK.sub("", text)
    text = _THINK_OPEN.sub("", text)                        # an unclosed block is still reasoning
    return re.sub(r"</?think>", "", text, flags=re.I)


def plain_answer(text: str | None) -> str:
    """The answer as a person would type it in a chat message."""
    if not text:
        return ""
    text = without_reasoning(text).translate(_LOOKALIKES)
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    fence: str | None = None
    skipping_sources = False
    for i, raw in enumerate(lines):
        opener = _FENCE.match(raw)
        if fence is not None:
            out.append(raw.rstrip())
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence) \
                    and not raw.strip()[len(opener.group(1)):].strip():
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            skipping_sources = False
            out.append(raw.rstrip())
            continue

        if skipping_sources:
            # The list under a "Sources:" header goes with it.
            if _LIST_ITEM.match(raw):
                continue
            if not raw.strip() and any(_LIST_ITEM.match(n) for n in lines[i + 1:i + 2]):
                continue
            skipping_sources = False

        if _RULE.match(raw) or _TABLE_SEP.match(raw):
            continue
        source = _SOURCE_LINE.match(raw)
        if source:
            rest = re.sub(r"[)*_\s]+$", "", source.group(2))
            if _is_empty_label(rest):
                skipping_sources = True
                continue
            trailing = not any(n.strip() for n in lines[i + 1:])
            has_body = any(o.strip() for o in out)
            if trailing and has_body and len(rest) <= 120 and not re.search(r"[.!?]$", rest):
                continue                                     # "Source: Confluence on-call rota" at the end
            raw = source.group(1) + rest                     # "Reference: the window is ..." keeps its content
        row = _table_row(raw)
        if row is not None:
            line = _inline(row)
        else:
            heading = _HEADING.match(raw)
            if heading:
                title = _inline(heading.group(1)).replace("**", "").strip()
                line = f"**{title}**" if title else ""
            else:
                line = _inline(_BULLET.sub(r"\1- ", raw))
        if re.fullmatch(r"\s*(?:[-*]|\d+\.)\s*", line or ""):
            continue                                         # a bullet emptied by the clean-up
        out.append(line)
    joined = "\n".join(out)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()
