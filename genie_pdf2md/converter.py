from __future__ import annotations

from pathlib import Path

from genie_core.pdf import split_pdf_to_images
from genie_core.llm import LMStudioClient


SYSTEM_PROMPT = """You are a document parser. Given an image of a PDF page, extract all visible content into well-structured Markdown.

Rules:
- Preserve headings, lists, tables, and formatting structure
- For tables, use Markdown table syntax
- For diagrams or charts, describe them in [Image: description] blocks
- Keep the original language (do not translate)
- Output ONLY the Markdown content, no explanations"""


def pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    vision_model: str = "qwen3-vl",
    lm_studio_url: str = "http://localhost:1234/v1",
    dpi: int = 200,
    progress_callback=None,
) -> dict:
    """Convert a PDF to per-page images + combined Markdown.

    Returns {"markdown": str, "html": str, "images_dir": str, "pages": int}.
    """
    pdf_path = str(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Step 1: Split PDF to images
    if progress_callback:
        progress_callback("splitting", 0)

    pages = split_pdf_to_images(pdf_path, str(images_dir), dpi=dpi)

    # Step 2: Parse each page with vision model
    llm = LMStudioClient(base_url=lm_studio_url, model=vision_model)
    markdown_parts = []

    for i, page in enumerate(pages):
        if progress_callback:
            progress_callback("parsing", (i + 1) / len(pages))

        page_md = llm.vision(
            prompt=f"Parse this PDF page (page {page['page']}) into Markdown.",
            image_path=page["path"],
            system=SYSTEM_PROMPT,
        )
        markdown_parts.append(f"<!-- Page {page['page']} -->\n\n{page_md}")

    # Step 3: Combine and write output
    full_markdown = "\n\n---\n\n".join(markdown_parts)

    md_path = output_dir / "output.md"
    md_path.write_text(full_markdown, encoding="utf-8")

    html_content = _markdown_to_html(full_markdown, pages)
    html_path = output_dir / "output.html"
    html_path.write_text(html_content, encoding="utf-8")

    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "images_dir": str(images_dir),
        "pages": len(pages),
    }


def _markdown_to_html(markdown_text: str, pages: list[dict]) -> str:
    """Simple Markdown-to-HTML with page images embedded."""
    lines = []
    lines.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    lines.append("<style>body{font-family:sans-serif;max-width:900px;margin:0 auto;padding:20px}")
    lines.append(".page{margin:40px 0;border-bottom:1px solid #ccc;padding-bottom:20px}")
    lines.append(".page img{max-width:100%;border:1px solid #ddd}</style></head><body>")

    page_sections = markdown_text.split("---")
    for i, section in enumerate(page_sections):
        lines.append(f'<div class="page">')
        if i < len(pages):
            rel_path = Path(pages[i]["path"]).name
            lines.append(f'<img src="images/{rel_path}" alt="Page {i+1}">')
        lines.append(f"<pre>{section.strip()}</pre>")
        lines.append("</div>")

    lines.append("</body></html>")
    return "\n".join(lines)
