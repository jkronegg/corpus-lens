#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional


LANGUAGE_STOPWORDS: dict[str, tuple[str, ...]] = {
    # Stopwords distinctifs par langue (pas de chevauchement)
    "fr": ("le", "les", "des", "du", "par", "avec", "très", "bien", "aussi", "cette", "celui", "ceux", "dont", "quel"),
    "de": ("der", "das", "und", "nicht", "sein", "mehr", "alle", "keine", "gegen", "über", "während", "weil", "bevor"),
    "it": ("gli", "lui", "lei", "loro", "stesso", "quale", "altro", "dove", "quando", "mentre", "dopo", "prima"),
    "en": ("the", "and", "that", "this", "these", "those", "been", "were", "have", "would", "could", "should", "their", "there"),
    "es": ("los", "las", "esta", "estas", "este", "estos", "esa", "esas", "ese", "esos", "mismo", "misma", "cuyo", "pueda"),
}

SKILL_NAME = "translate-markdown"


def parse_front_matter(markdown_text: str) -> tuple[Optional[str], str]:
    if not markdown_text.startswith("---\n"):
        return None, markdown_text

    match = re.match(r"(?s)^---\n(.*?)\n---\n?", markdown_text)
    if not match:
        return None, markdown_text

    fm_body = match.group(1)
    body = markdown_text[match.end():]
    return fm_body, body


def serialize_front_matter(front_matter_body: str) -> str:
    return f"---\n{front_matter_body.rstrip()}\n---\n\n"


def upsert_front_matter_field(front_matter_body: str, key: str, value: str) -> str:
    escaped = value.replace('"', "'")
    serialized_value = f'"{escaped}"'

    lines = front_matter_body.splitlines() if front_matter_body else []
    key_pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*)$")

    for idx, line in enumerate(lines):
        if key_pattern.match(line):
            lines[idx] = f"{key}: {serialized_value}"
            return "\n".join(lines)

    lines.append(f"{key}: {serialized_value}")
    return "\n".join(lines)


def detect_language_distribution(text: str) -> list[tuple[str, int]]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ']+", text.lower())
    if not tokens:
        return [("unknown", 100)]

    counts: dict[str, int] = {lang: 0 for lang in LANGUAGE_STOPWORDS}
    for token in tokens:
        for lang, words in LANGUAGE_STOPWORDS.items():
            if token in words:
                counts[lang] += 1

    total = sum(counts.values())
    if total == 0:
        return [("unknown", 100)]

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ranked = [item for item in ranked if item[1] > 0]

    percentages: list[tuple[str, int]] = []
    consumed = 0
    for idx, (lang, score) in enumerate(ranked):
        if idx == len(ranked) - 1:
            pct = 100 - consumed
        else:
            pct = int(round((score / total) * 100))
            consumed += pct
        percentages.append((lang, max(0, pct)))

    percentages.sort(key=lambda kv: (-kv[1], kv[0]))
    return percentages


def format_distribution(distribution: list[tuple[str, int]]) -> str:
    return ", ".join(f"{lang}:{pct}" for lang, pct in distribution)


def update_source_front_matter(*, source_text: str, distribution: str) -> str:
    front_matter_body, body = parse_front_matter(source_text)
    out_fm = front_matter_body or ""
    out_fm = upsert_front_matter_field(out_fm, "skill", SKILL_NAME)
    out_fm = upsert_front_matter_field(out_fm, "language_distribution", distribution)
    return serialize_front_matter(out_fm) + body.lstrip("\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect language distribution in a Markdown file.")
    parser.add_argument("--input", dest="input_path", type=Path, required=True, help="Input Markdown file")
    parser.add_argument(
        "--output",
        dest="output_path",
        type=Path,
        default=None,
        help="Output Markdown file (default: overwrite input)",
    )
    parser.add_argument("--write", action="store_true", help="Write updated front matter to file")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    source_text = args.input_path.read_text(encoding="utf-8", errors="replace")
    _, body = parse_front_matter(source_text)

    distribution_list = detect_language_distribution(body)
    distribution = format_distribution(distribution_list)

    print(distribution)

    if not args.write:
        return 0

    output_text = update_source_front_matter(source_text=source_text, distribution=distribution)
    output_path = args.output_path or args.input_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")
    print(f"ok: updated front matter -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

