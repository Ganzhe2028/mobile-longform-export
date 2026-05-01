#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import render_mobile_reader_v3 as renderer


APP_SUPPORT = Path.home() / "Library/Application Support/MobileLongformExport"
CONFIG_PATH = APP_SUPPORT / "config.json"
DEFAULT_OUTPUT_ROOT = Path.home() / "Downloads/MobileLongformExports"
DEFAULT_AUTHOR = "Isaac's Agent"
DEFAULT_PREFIX = "mobile-longform"


@dataclass
class ExportResult:
    source: str
    title: str
    out_dir: Path
    pdf_path: Path
    page_count: int


def load_config():
    defaults = {
        "author": DEFAULT_AUTHOR,
        "output_root": str(DEFAULT_OUTPUT_ROOT),
        "reveal": True,
        "copy_pdf_path": True,
    }
    if not CONFIG_PATH.exists():
        return defaults
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    merged = dict(defaults)
    for key in defaults:
        if key in data:
            merged[key] = data[key]
    return merged


def read_clipboard():
    proc = subprocess.run(
        ["/usr/bin/pbpaste"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    text = proc.stdout
    if not text.strip():
        raise ValueError("Clipboard is empty.")
    return text


def clean_title_text(text):
    text = text.strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = text.replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", text).strip()


def fallback_title_from_clipboard(text):
    for line in text.splitlines():
        title = clean_title_text(line)
        if 0 < len(title) <= 80:
            return title
    return "Markdown Export"


def title_from_markdown_text(text, fallback):
    title, _ = renderer.parse_markdown_text(text, fallback)
    return title


def slugify_title(title):
    title = clean_title_text(title)
    chunks = re.findall(r"[A-Za-z0-9]+|[一-鿿]+", title)
    slug = "-".join(chunks).strip("-")
    if not slug:
        slug = "Markdown-Export"
    return slug[:60].strip("-") or "Markdown-Export"


def unique_output_dir(output_root, title):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = output_root / f"{timestamp}-{slugify_title(title)}"
    if not base.exists():
        return base
    for idx in range(2, 1000):
        candidate = output_root / f"{base.name}-{idx}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique output directory under {output_root}")


def render_file(path, output_root, author, max_pages=None):
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding="utf-8")
    title = title_from_markdown_text(raw, path.stem)
    out_dir = unique_output_dir(output_root, title)
    page_count, pdf_path = renderer.render(path, out_dir, DEFAULT_PREFIX, max_pages=max_pages, author=author)
    return ExportResult(str(path), title, out_dir, pdf_path, page_count)


def render_clipboard(output_root, author, max_pages=None):
    raw = read_clipboard()
    fallback_title = fallback_title_from_clipboard(raw)
    title = title_from_markdown_text(raw, fallback_title)
    out_dir = unique_output_dir(output_root, title)
    page_count, pdf_path = renderer.render_markdown_text(
        raw,
        out_dir,
        DEFAULT_PREFIX,
        max_pages=max_pages,
        author=author,
        fallback_title=fallback_title,
    )
    return ExportResult("clipboard", title, out_dir, pdf_path, page_count)


def copy_pdf_path(pdf_path):
    subprocess.run(
        ["/usr/bin/pbcopy"],
        check=True,
        text=True,
        input=str(pdf_path),
    )


def reveal_path(path):
    subprocess.run(["/usr/bin/open", str(path)], check=False)


def resolve_bool(cli_value, config_value):
    if cli_value is not None:
        return cli_value
    return bool(config_value)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export Markdown into iPhone-readable PDF and paged PNG files.",
    )
    parser.add_argument("--input", nargs="+", type=Path, help="Markdown file path(s) to export.")
    parser.add_argument("--clipboard", action="store_true", help="Export Markdown text from the clipboard.")
    parser.add_argument("--author", default=None, help="Author name shown in the metadata line.")
    parser.add_argument("--hide-author", action="store_true", help="Hide the author name and show only the date.")
    parser.add_argument("--output-root", type=Path, default=None, help="Root directory for exports.")
    parser.add_argument("--max-pages", type=int, default=None, help="Render only the first N pages.")
    parser.add_argument("--reveal", dest="reveal", action="store_true", default=None, help="Open Finder after export.")
    parser.add_argument("--no-reveal", dest="reveal", action="store_false", help="Do not open Finder after export.")
    parser.add_argument(
        "--copy-pdf-path",
        dest="copy_pdf_path",
        action="store_true",
        default=None,
        help="Copy the final PDF path to the clipboard.",
    )
    parser.add_argument(
        "--no-copy-pdf-path",
        dest="copy_pdf_path",
        action="store_false",
        help="Do not copy the PDF path to the clipboard.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    output_root = (args.output_root or Path(config["output_root"])).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    author = "" if args.hide_author else (args.author if args.author is not None else str(config["author"]))
    reveal = resolve_bool(args.reveal, config["reveal"])
    should_copy_pdf = resolve_bool(args.copy_pdf_path, config["copy_pdf_path"])

    if not args.input and not args.clipboard:
        args.clipboard = True

    results = []
    for path in args.input or []:
        results.append(render_file(path, output_root, author, args.max_pages))
    if args.clipboard:
        results.append(render_clipboard(output_root, author, args.max_pages))

    if not results:
        raise ValueError("No Markdown input was provided.")

    if should_copy_pdf:
        copy_pdf_path(results[-1].pdf_path)
    if reveal:
        reveal_path(output_root if len(results) > 1 else results[0].out_dir)

    for result in results:
        print(f"source: {result.source}")
        print(f"title: {result.title}")
        print(f"pages: {result.page_count}")
        print(f"pdf: {result.pdf_path}")
        print(f"folder: {result.out_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Mobile Longform Export failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
