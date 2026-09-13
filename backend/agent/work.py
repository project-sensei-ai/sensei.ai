"""
Work the colleague can hand back as a file.

"Make me a spreadsheet of the open issues by owner" is a request a teammate
fulfils by producing a file, not a paragraph. These tools let the agent do the
same. Each produces an artifact on disk, records it in a list the chat route
persists, and returns a download path the answer can link to.

Deliberately small: spreadsheets and documents cover most of what people ask a
colleague to "put together". Anything system-specific (a Jira ticket, a
Confluence page, an email) goes through a tool grant, where the owner has
decided whether writes are allowed.
"""
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from strands import tool

from core.config import settings


def artifacts_dir(workspace_id: str) -> str:
    path = os.path.join(settings.CHROMA_PERSIST_DIR, "artifacts", workspace_id)
    os.makedirs(path, exist_ok=True)
    return path


def _safe_name(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", (title or "untitled").strip()).strip("-")[:60] or "untitled"
    return f"{base}.{ext}"


def make_work_tools(workspace_id: str, created_by: str):
    """Returns (tools, produced) — `produced` fills as the agent makes files."""
    produced: list[dict] = []
    folder = artifacts_dir(workspace_id)

    def _record(title: str, filename: str, path: str, mime: str, kind: str, summary: str) -> dict:
        art = {
            "_id": uuid4().hex,
            "workspace_id": workspace_id,
            "title": title,
            "filename": filename,
            "path": path,
            "mime": mime,
            "kind": kind,
            "summary": summary,
            "size": os.path.getsize(path),
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        produced.append(art)
        return art

    @tool
    def create_spreadsheet(title: str, columns: list[str], rows: list[list[str]]) -> str:
        """
        Create an Excel spreadsheet (.xlsx) and hand it to the person as a download.

        Use when someone asks for a table, a sheet, a tracker, a list they can
        sort or share — "make me an excel of…", "put that in a spreadsheet".
        `columns` are the header cells; `rows` is a list of rows, each a list of
        cell values in the same order as `columns`. Keep values as plain strings
        or numbers. Gather the data with your other tools FIRST, then call this
        once with everything.
        """
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = (title or "Sheet")[:30]
        ws.append([str(c) for c in columns])
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="E8EEF7")
        for r in rows:
            ws.append([("" if v is None else v) for v in list(r)[: len(columns)]])
        for i, col in enumerate(columns, start=1):
            width = max([len(str(col))] + [len(str(r[i - 1])) for r in rows if len(r) >= i]) if rows else len(str(col))
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
        ws.freeze_panes = "A2"

        filename = _safe_name(title, "xlsx")
        path = os.path.join(folder, f"{uuid4().hex[:8]}_{filename}")
        wb.save(path)
        art = _record(
            title, filename, path,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "spreadsheet", f"{len(rows)} rows × {len(columns)} columns",
        )
        return (
            f"Created spreadsheet '{title}' with {len(rows)} rows and {len(columns)} columns. "
            f"It is attached to your reply as a download (artifact {art['_id']}). "
            "Tell the person it is attached below; do not invent a URL."
        )

    @tool
    def write_document(title: str, markdown: str, format: str = "docx") -> str:
        """
        Write a document and hand it to the person as a download.

        Use for anything a colleague would send as a file rather than a chat
        message: a summary for a stakeholder, meeting notes, a runbook draft, a
        handover note. `markdown` is the full body (headings with #, bullets
        with -). `format` is "docx" (Word, default) or "md".
        """
        fmt = "md" if str(format).lower().strip(". ") == "md" else "docx"
        filename = _safe_name(title, fmt)
        path = os.path.join(folder, f"{uuid4().hex[:8]}_{filename}")

        if fmt == "md":
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n{markdown}")
            mime = "text/markdown"
        else:
            from docx import Document
            doc = Document()
            doc.add_heading(title, level=0)
            for line in markdown.splitlines():
                s = line.rstrip()
                if not s:
                    continue
                if s.startswith("### "):
                    doc.add_heading(s[4:], level=3)
                elif s.startswith("## "):
                    doc.add_heading(s[3:], level=2)
                elif s.startswith("# "):
                    doc.add_heading(s[2:], level=1)
                elif re.match(r"^\s*[-*] ", s):
                    doc.add_paragraph(re.sub(r"^\s*[-*] ", "", s), style="List Bullet")
                elif re.match(r"^\s*\d+[.)] ", s):
                    doc.add_paragraph(re.sub(r"^\s*\d+[.)] ", "", s), style="List Number")
                else:
                    doc.add_paragraph(s)
            doc.save(path)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        words = len(markdown.split())
        art = _record(title, filename, path, mime, "document", f"{words} words")
        return (
            f"Wrote '{title}' ({words} words) as a .{fmt} file. It is attached to your "
            f"reply as a download (artifact {art['_id']}). Tell the person it is attached "
            "below; do not invent a URL."
        )

    return [create_spreadsheet, write_document], produced
