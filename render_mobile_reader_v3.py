#!/usr/bin/env python3
import argparse
import datetime as dt
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DPR = 3
PAGE_W = 402 * DPR
PAGE_H = 874 * DPR

MARGIN_X = 28 * DPR
CONTENT_TOP = 48 * DPR
CONTENT_BOTTOM = PAGE_H - 64 * DPR
CONTENT_W = PAGE_W - MARGIN_X * 2

INK = (28, 29, 31)
SECONDARY = (88, 93, 102)
FOOTER = (126, 132, 143)
WHITE = (255, 255, 255)

SF_PRO = "/System/Library/Fonts/SFNS.ttf"
PINGFANG = (
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/"
    "86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc"
)
PINGFANG_SC_REGULAR = 3
PINGFANG_SC_MEDIUM = 7
PINGFANG_SC_SEMIBOLD = 11

LINE_START_FORBIDDEN = set("，。！？；：、,.!?;:)]}）】》”’」』…—")
LINE_END_FORBIDDEN = set("([{（【《“‘「『")
TRAILING_PUNCT = set("，。！？；：、,.!?;:)]}）】》”’」』")
MIXED_SCRIPT_SPACE = "\u2009"


def load_font(path, size, index=0, variation_name=None):
    font = ImageFont.truetype(path, size=size, index=index)
    if variation_name and hasattr(font, "set_variation_by_name"):
        font.set_variation_by_name(variation_name)
    return font


def make_style(size, line_h, cjk_index=PINGFANG_SC_REGULAR, color=INK, latin_weight="Regular"):
    latin = load_font(SF_PRO, size, variation_name=latin_weight)
    cjk = load_font(PINGFANG, size, cjk_index)
    latin_ascent, latin_descent = latin.getmetrics()
    cjk_ascent, cjk_descent = cjk.getmetrics()
    return {
        "latin": latin,
        "cjk": cjk,
        "latin_ascent": latin_ascent,
        "cjk_ascent": cjk_ascent,
        "line_ascent": max(latin_ascent, cjk_ascent),
        "line_descent": max(latin_descent, cjk_descent),
        "mixed_gap": max(7, round(size * 0.18)),
        "latin_tracking": max(1.0, round(size * 0.035, 1)),
        "size": size,
        "line_h": line_h,
        "color": color,
        "latin_weight": latin_weight,
    }


STYLES = {
    "title": make_style(63, 78, PINGFANG_SC_SEMIBOLD, INK, "Semibold"),
    "h2": make_style(54, 72, PINGFANG_SC_SEMIBOLD, INK, "Semibold"),
    "body": make_style(50, 82, PINGFANG_SC_REGULAR, INK),
    "meta": make_style(36, 50, PINGFANG_SC_REGULAR, SECONDARY),
    "footer": make_style(36, 44, PINGFANG_SC_REGULAR, FOOTER),
}


def strip_front_matter(text):
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
    return text


def normalize_quotes(text):
    result = []
    double_open = True
    single_open = True
    for i, ch in enumerate(text):
        if ch == '"':
            result.append("“" if double_open else "”")
            double_open = not double_open
            continue
        if ch == "'":
            prev_ch = text[i - 1] if i else ""
            next_ch = text[i + 1] if i + 1 < len(text) else ""
            if prev_ch.isalpha() and next_ch.isalpha():
                result.append("’")
            else:
                result.append("‘" if single_open else "’")
                single_open = not single_open
            continue
        result.append(ch)
    return "".join(result)


def normalize_text(text):
    text = normalize_quotes(text)
    text = text.replace("...", "……")
    text = re.sub(r"(?<!…)…(?!…)", "……", text)
    text = re.sub(r"--+", "——", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([A-Za-z0-9])\s*([一-鿿])", rf"\1{MIXED_SCRIPT_SPACE}\2", text)
    text = re.sub(r"([一-鿿])\s*([A-Za-z0-9])", rf"\1{MIXED_SCRIPT_SPACE}\2", text)
    return text.strip()


def clean_inline(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = text.replace("*", "").replace("_", "")
    return normalize_text(text)


def needs_space(left, right):
    if not left or not right:
        return False
    return left[-1].isascii() and right[0].isascii() and left[-1].isalnum() and right[0].isalnum()


def combine_paragraph(lines):
    out = ""
    for item in lines:
        part = item.strip()
        if not part:
            continue
        if out and needs_space(out, part):
            out += " "
        out += part
    return out


def parse_markdown_text(raw, fallback_title="Markdown Export"):
    raw = strip_front_matter(raw)
    blocks = []
    title = None
    paragraph = []

    def flush_para():
        nonlocal paragraph
        if paragraph:
            blocks.append(("p", clean_inline(combine_paragraph(paragraph))))
            paragraph = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_para()
            continue
        if stripped.startswith("# "):
            flush_para()
            value = clean_inline(stripped[2:])
            if title is None:
                title = value
            else:
                blocks.append(("h1", value))
            continue
        if stripped.startswith("## "):
            flush_para()
            blocks.append(("h2", clean_inline(stripped[3:])))
            continue
        if stripped.startswith(">"):
            paragraph.append(stripped.lstrip("> "))
            continue
        if stripped.startswith(("- ", "* ")):
            flush_para()
            blocks.append(("p", "• " + clean_inline(stripped[2:])))
            continue
        paragraph.append(stripped)

    flush_para()
    blocks = merge_short_bridge_paragraphs(blocks)
    return title or fallback_title or "Markdown Export", blocks


def parse_markdown(path):
    return parse_markdown_text(path.read_text(encoding="utf-8"), path.stem)


def is_latin_char(ch):
    return ord(ch) < 256 or ch == MIXED_SCRIPT_SPACE


def is_cjk(ch):
    return "\u4e00" <= ch <= "\u9fff"


def short_bridge_text(text):
    clean = strip_trailing_punct(text)
    return text.endswith(("：", ":")) and 0 < sum(1 for ch in clean if is_cjk(ch)) < 3


def merge_short_bridge_paragraphs(blocks):
    merged = []
    i = 0
    while i < len(blocks):
        kind, text = blocks[i]
        if kind == "p" and short_bridge_text(text) and i + 1 < len(blocks) and blocks[i + 1][0] == "p":
            merged.append(("p", text + blocks[i + 1][1]))
            i += 2
            continue
        merged.append((kind, text))
        i += 1
    return merged


def font_for_char(ch, style):
    return style["latin"] if is_latin_char(ch) else style["cjk"]


def text_width(draw, text, style):
    width = 0
    for idx, ch in enumerate(text):
        width += char_width(draw, ch, style)
        width += tracking_after(text, idx, style)
    return width


def char_width(draw, ch, style):
    if ch == MIXED_SCRIPT_SPACE:
        return style["mixed_gap"]
    return draw.textlength(ch, font=font_for_char(ch, style))


def is_latin_word_letter(ch):
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


def is_ascii_word_char(ch):
    return ord(ch) < 128 and (ch.isalnum() or ch in "-_./:@")


def tracking_after(text, idx, style):
    ch = text[idx]
    if idx + 1 >= len(text):
        return 0
    nxt = text[idx + 1]
    if is_latin_word_letter(ch) and is_latin_word_letter(nxt):
        return style["latin_tracking"]
    return 0


def emergency_split_ascii_word(draw, word, style, max_width):
    parts = []
    current = ""
    for ch in word:
        candidate = current + ch
        if current and text_width(draw, candidate + "-", style) > max_width:
            parts.append(current + "-")
            current = ch
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def token_chunks(text):
    chunks = []
    buf = ""
    i = 0
    while i < len(text):
        ch = text[i]
        pair = text[i : i + 2]
        if pair in {"——", "……"}:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(pair)
            i += 2
            continue
        is_word = ord(ch) < 128 and (ch.isalnum() or ch in "-_./:@")
        if is_word:
            buf += ch
            i += 1
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        chunks.append(ch)
        i += 1
    if buf:
        chunks.append(buf)
    return chunks

def strip_trailing_punct(text):
    return "".join(ch for ch in text.strip() if ch not in TRAILING_PUNCT and not ch.isspace())


def is_runt_line(line):
    clean = strip_trailing_punct(line)
    if not clean:
        return True
    cjk_count = sum(1 for ch in clean if is_cjk(ch))
    latin_words = re.findall(r"[A-Za-z]+", clean)
    other = re.sub(r"[A-Za-z一-鿿0-9]", "", clean)
    if cjk_count and cjk_count < 3 and not latin_words:
        return True
    if len(latin_words) == 1 and len(latin_words[0]) < 7 and cjk_count == 0 and not other:
        return True
    return False


def steal_tail_for_runt(previous):
    if not previous:
        return previous, ""
    match = re.search(r"([A-Za-z0-9-]+[，。！？；：、,.!?;:]*|[一-鿿]{1,3}[，。！？；：、,.!?;:]*)$", previous.strip())
    if not match:
        return previous, ""
    moved = match.group(1)
    trimmed = previous[: match.start()].rstrip()
    if len(strip_trailing_punct(trimmed)) < 5:
        return previous, ""
    return trimmed, moved


def repair_runt_last_line(lines):
    if len(lines) < 2 or not is_runt_line(lines[-1]):
        return lines
    repaired = list(lines)
    for _ in range(2):
        previous, moved = steal_tail_for_runt(repaired[-2])
        if not moved:
            break
        repaired[-2] = previous
        sep = "" if moved.endswith("-") else ""
        repaired[-1] = (moved + sep + repaired[-1]).strip()
        if not is_runt_line(repaired[-1]):
            break
    return repaired


def repair_forbidden_line_edges(lines):
    repaired = [line for line in lines if line]
    i = 1
    while i < len(repaired):
        line = repaired[i]
        if line and line[0] in LINE_START_FORBIDDEN:
            repaired[i - 1] = (repaired[i - 1] + line[0]).rstrip()
            repaired[i] = line[1:].lstrip()
            if not repaired[i]:
                repaired.pop(i)
                continue
        i += 1

    i = 0
    while i < len(repaired) - 1:
        line = repaired[i]
        if line and line[-1] in LINE_END_FORBIDDEN:
            repaired[i] = line[:-1].rstrip()
            repaired[i + 1] = (line[-1] + repaired[i + 1]).lstrip()
            if not repaired[i]:
                repaired.pop(i)
                continue
        i += 1
    return repaired


def wrap_text(draw, text, style, max_width, repair_runt=True):
    chunks = token_chunks(text)
    lines = []
    line = ""

    for chunk in chunks:
        candidate = line + chunk
        if text_width(draw, candidate, style) <= max_width:
            line = candidate
            continue

        if chunk[0] in LINE_START_FORBIDDEN and line:
            lines.append((line + chunk).strip())
            line = ""
            continue

        if line and line[-1] in LINE_END_FORBIDDEN:
            opener = line[-1]
            line = line[:-1].rstrip()
            chunk = opener + chunk

        if line:
            lines.append(line.strip())
            line = chunk.lstrip()
        else:
            if text_width(draw, chunk, style) > max_width and re.fullmatch(r"[A-Za-z0-9_./:@-]+", chunk):
                parts = emergency_split_ascii_word(draw, chunk, style, max_width)
                lines.extend(parts[:-1])
                line = parts[-1]
                continue
            lines.append(chunk)
            line = ""

    if line:
        lines.append(line.strip())

    lines = repair_forbidden_line_edges(lines)
    if repair_runt:
        lines = repair_runt_last_line(lines)
        lines = repair_forbidden_line_edges(lines)
    return lines or [""]


def make_unit(kind, lines, style, gap_before, gap_after):
    return {
        "kind": kind,
        "lines": lines,
        "style": style,
        "gap_before": gap_before,
        "gap_after": gap_after,
    }


def format_meta_line(author):
    today = dt.date.today()
    date_text = f"{today.year}.{today.month}.{today.day}"
    if author:
        return f"{author} · {date_text}"
    return date_text


def build_units(title, blocks, author="Isaac's Agent"):
    scratch = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
    draw = ImageDraw.Draw(scratch)
    units = [
        make_unit("title", wrap_text(draw, title, STYLES["title"], CONTENT_W, False), STYLES["title"], 0, 36),
        make_unit("meta", [format_meta_line(author)], STYLES["meta"], 0, 74),
    ]

    for kind, text in blocks:
        if kind in {"h1", "h2"}:
            units.append(
                make_unit(
                    "h2",
                    wrap_text(draw, text, STYLES["h2"], CONTENT_W, False),
                    STYLES["h2"],
                    82,
                    36,
                )
            )
        else:
            units.append(
                make_unit(
                    "p",
                    wrap_text(draw, text, STYLES["body"], CONTENT_W, True),
                    STYLES["body"],
                    0,
                    58,
                )
            )
    return units


def unit_height(unit):
    return unit["gap_before"] + len(unit["lines"]) * unit["style"]["line_h"] + unit["gap_after"]


def split_text_unit(unit, available_h):
    line_room = max(1, math.floor((available_h - unit["gap_before"]) / unit["style"]["line_h"]))
    if unit["kind"] == "p" and 0 < len(unit["lines"]) - line_room < 2:
        line_room = max(1, line_room - 1)
    head = dict(unit)
    tail = dict(unit)
    head["lines"] = unit["lines"][:line_room]
    head["gap_after"] = 0
    tail["lines"] = unit["lines"][line_room:]
    tail["gap_before"] = 0
    return head, tail


def paginate(units):
    pages = []
    page = []
    y = CONTENT_TOP
    i = 0

    while i < len(units):
        unit = units[i]
        h = unit_height(unit)

        if unit["kind"] == "h2" and page:
            next_min = STYLES["body"]["line_h"] * 3
            if y + h + next_min > CONTENT_BOTTOM:
                pages.append(page)
                page = []
                y = CONTENT_TOP
                continue

        if page and y + h > CONTENT_BOTTOM:
            remaining = CONTENT_BOTTOM - y
            line_room = math.floor((remaining - unit["gap_before"]) / unit["style"]["line_h"])
            if unit["kind"] == "p" and line_room >= 4:
                head, tail = split_text_unit(unit, remaining)
                page.append(head)
                pages.append(page)
                page = []
                y = CONTENT_TOP
                units[i] = tail
                continue
            pages.append(page)
            page = []
            y = CONTENT_TOP
            continue

        if y + h <= CONTENT_BOTTOM:
            page.append(unit)
            y += h
            i += 1
            continue

        head, tail = split_text_unit(unit, CONTENT_BOTTOM - y)
        page.append(head)
        pages.append(page)
        page = []
        y = CONTENT_TOP
        units[i] = tail

    if page:
        pages.append(page)
    return pages


def draw_mixed_text(draw, xy, text, style):
    x, y = xy
    baseline_y = y + style["line_ascent"]
    for idx, ch in enumerate(text):
        if ch == MIXED_SCRIPT_SPACE:
            x += style["mixed_gap"]
            continue
        fnt = font_for_char(ch, style)
        draw.text((x, baseline_y), ch, fill=style["color"], font=fnt, anchor="ls")
        x += draw.textlength(ch, font=fnt)
        x += tracking_after(text, idx, style)


def draw_page(units, page_no, total):
    img = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
    draw = ImageDraw.Draw(img)

    y = CONTENT_TOP
    for unit in units:
        y += unit["gap_before"]
        for line in unit["lines"]:
            draw_mixed_text(draw, (MARGIN_X, y), line, unit["style"])
            y += unit["style"]["line_h"]
        y += unit["gap_after"]

    footer = f"{page_no}/{total}"
    footer_w = text_width(draw, footer, STYLES["footer"])
    draw_mixed_text(draw, (PAGE_W - MARGIN_X - footer_w, PAGE_H - 43 * DPR), footer, STYLES["footer"])
    return img


def render_blocks(title, blocks, out_dir, prefix, max_pages=None, author="Isaac's Agent"):
    units = build_units(title, blocks, author)
    pages = paginate(units)
    if max_pages:
        pages = pages[:max_pages]

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{prefix}-page-*.png"):
        old.unlink()
    old_pdf = out_dir / f"{prefix}.reader-screen-pages.pdf"
    if old_pdf.exists():
        old_pdf.unlink()

    images = []
    for idx, page in enumerate(pages, start=1):
        img = draw_page(page, idx, len(pages))
        out = out_dir / f"{prefix}-page-{idx:02d}.png"
        img.save(out, "PNG")
        images.append(img)

    pdf_path = out_dir / f"{prefix}.reader-screen-pages.pdf"
    if images:
        images[0].save(pdf_path, "PDF", save_all=True, append_images=images[1:])
    return len(images), pdf_path


def render_markdown_text(raw, out_dir, prefix, max_pages=None, author="Isaac's Agent", fallback_title="Markdown Export"):
    title, blocks = parse_markdown_text(raw, fallback_title)
    return render_blocks(title, blocks, out_dir, prefix, max_pages, author)


def render(md_path, out_dir, prefix, max_pages=None, author="Isaac's Agent"):
    title, blocks = parse_markdown(md_path)
    return render_blocks(title, blocks, out_dir, prefix, max_pages, author)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--prefix", default="mobile-reader-v3")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--author",
        default="Isaac's Agent",
        help="Author name shown in the metadata line. Pass an empty string to show the date only.",
    )
    parser.add_argument(
        "--hide-author",
        action="store_true",
        help="Hide the author name and keep only the date in the metadata line.",
    )
    args = parser.parse_args()
    author = "" if args.hide_author else args.author
    count, pdf_path = render(args.markdown, args.out, args.prefix, args.max_pages, author)
    print(f"rendered {count} PNG pages")
    print(pdf_path)


if __name__ == "__main__":
    main()
