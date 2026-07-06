from __future__ import annotations

import logging
import re
from pathlib import Path

from genie_core.pdf import split_pdf_to_images
from genie_core.llm import LMStudioClient, DEFAULT_BASE_URL
from genie_core.report import html_page, esc


SYSTEM_PROMPT = """You are a document parser. Given an image of a PDF page, extract all visible content into well-structured Markdown.

Rules:
- Preserve headings, lists, tables, and formatting structure
- For tables, use Markdown table syntax
- For diagrams or charts, describe them in [Image: description] blocks
- Keep the original language (do not translate)
- Output ONLY the Markdown content, no explanations"""

_FAILED_MARKER = "<!-- page %d failed:"

_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*?)\r?\n?```\s*$", re.DOTALL)


def pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    vision_model: str = "qwen3-vl",
    lm_studio_url: str = DEFAULT_BASE_URL,
    dpi: int = 200,
    progress_callback=None,
) -> dict:
    """Convert a PDF to per-page images + combined Markdown.

    Each page's Markdown is written to pages/page_NNN.md as soon as it is
    parsed, so an interrupted run can be resumed: existing (successful) page
    files are reused without re-calling the vision model. A page whose vision
    call fails (after one retry) gets a placeholder comment and the run
    continues.

    Returns {"markdown": str, "html": str, "images_dir": str, "pages": int,
    "failed_pages": list[int]}.
    """
    pdf_path = str(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    pages_dir = output_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    # Step 1: Split PDF to images
    if progress_callback:
        progress_callback("splitting", 0)

    pages = split_pdf_to_images(pdf_path, str(images_dir), dpi=dpi)

    # Step 2: Parse each page with vision model (per-page files, resumable)
    llm = LMStudioClient(base_url=lm_studio_url, model=vision_model)
    markdown_parts = []
    failed_pages = []

    for i, page in enumerate(pages):
        if progress_callback:
            progress_callback("parsing", (i + 1) / len(pages))

        page_no = page["page"]
        page_md_path = pages_dir / ("page_%03d.md" % page_no)

        page_md = None
        if page_md_path.exists():
            existing = page_md_path.read_text(encoding="utf-8")
            if existing.startswith(_FAILED_MARKER % page_no):
                # Previous run failed this page: retry it.
                page_md = None
            else:
                page_md = existing

        if page_md is None:
            try:
                page_md = _vision_with_retry(llm, page_no, page["path"])
                page_md = _strip_code_fence(page_md)
            except Exception as exc:
                logging.warning(
                    "Vision parsing failed for page %d (%s): %s",
                    page_no, page["path"], exc,
                )
                failed_pages.append(page_no)
                page_md = "%s %s -->" % (_FAILED_MARKER % page_no, exc)
            page_md_path.write_text(page_md, encoding="utf-8")

        markdown_parts.append("<!-- Page %d -->\n\n%s" % (page_no, page_md))

    # Step 3: Combine and write output
    full_markdown = "\n\n---\n\n".join(markdown_parts)

    md_path = output_dir / "output.md"
    md_path.write_text(full_markdown, encoding="utf-8")

    html_content = _markdown_to_html(markdown_parts, pages)
    html_path = output_dir / "output.html"
    html_path.write_text(html_content, encoding="utf-8")

    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "images_dir": str(images_dir),
        "pages": len(pages),
        "failed_pages": failed_pages,
    }


def _vision_with_retry(llm: LMStudioClient, page_no: int, image_path: str) -> str:
    """Call the vision model, retrying once on failure."""
    prompt = "Parse this PDF page (page %d) into Markdown." % page_no
    try:
        return llm.vision(prompt=prompt, image_path=image_path, system=SYSTEM_PROMPT)
    except Exception as exc:
        logging.warning(
            "Vision call failed for page %d, retrying once: %s", page_no, exc
        )
        return llm.vision(prompt=prompt, image_path=image_path, system=SYSTEM_PROMPT)


def _strip_code_fence(text: str) -> str:
    """Strip a single wrapping code fence (```markdown ... ```) if present."""
    match = _FENCE_RE.match(text.strip())
    if match:
        return match.group(1)
    return text


_PAGE_CSS = """
body { font-family: sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
.page { margin: 40px 0; border-bottom: 1px solid #ccc; padding-bottom: 20px; }
.page img { max-width: 100%; border: 1px solid #ddd; }
.page pre { white-space: pre-wrap; background: #f6f8fa; padding: 1em; border-radius: 6px; overflow-x: auto; }
""".strip()


def _markdown_to_html(markdown_parts: list[str], pages: list[dict]) -> str:
    """Render one section per page: page image + its (escaped) Markdown text.

    markdown_parts and pages line up index-for-index, so page images always
    match their text (no re-splitting of the combined Markdown).
    """
    body = []
    for i, section in enumerate(markdown_parts):
        body.append('<div class="page">')
        if i < len(pages):
            rel_path = Path(pages[i]["path"]).name
            body.append(
                '<img src="images/%s" alt="Page %d">' % (esc(rel_path), i + 1)
            )
        body.append("<pre>%s</pre>" % esc(section.strip()))
        body.append("</div>")

    title = "PDF to Markdown (%d pages)" % len(pages)
    return html_page(title, "\n".join(body), css=_PAGE_CSS)
