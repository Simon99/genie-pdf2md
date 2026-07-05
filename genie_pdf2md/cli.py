import argparse
import sys
from pathlib import Path

from .converter import pdf_to_markdown


def main():
    parser = argparse.ArgumentParser(description="Convert PDF to page images + Markdown")
    parser.add_argument("input", help="Path to PDF file")
    parser.add_argument("-o", "--output", help="Output directory (default: <input>_output/)")
    parser.add_argument("--model", default="qwen3-vl", help="Vision model name (default: qwen3-vl)")
    parser.add_argument("--url", default="http://localhost:1234/v1", help="LM Studio API URL")
    parser.add_argument("--dpi", type=int, default=200, help="Image DPI (default: 200)")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output or str(input_path.with_suffix("")) + "_output"

    def on_progress(stage, pct):
        stages = {"splitting": "Splitting PDF", "parsing": "Parsing pages"}
        label = stages.get(stage, stage)
        print(f"\r[{pct:.0%}] {label}...", end="", flush=True)

    print(f"Processing: {input_path}")
    result = pdf_to_markdown(
        str(input_path),
        output_dir,
        vision_model=args.model,
        lm_studio_url=args.url,
        dpi=args.dpi,
        progress_callback=on_progress,
    )
    print(f"\nDone! {result['pages']} pages")
    print(f"  Markdown: {result['markdown']}")
    print(f"  HTML: {result['html']}")
    print(f"  Images: {result['images_dir']}")


if __name__ == "__main__":
    main()
