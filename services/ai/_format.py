"""Markdown → Telegram-HTML fallback.

The AI is instructed to output HTML, but providers sometimes slip into Markdown
(especially for headings, bold, italic). This converter normalizes the most
common offenders into Telegram-supported tags before publishing.

It is intentionally conservative — only handles patterns Telegram accepts,
and leaves anything HTML-looking alone.
"""
from __future__ import annotations

import html
import re

_FENCE_RE = re.compile(r"```(\w+)?\n?(.*?)```", re.DOTALL)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_ALT_RE = re.compile(r"__(.+?)__", re.DOTALL)
_ITALIC_STAR_RE = re.compile(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.DOTALL)
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<![_\w])_(?!\s)(.+?)(?<!\s)_(?!_)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+?)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_HR_RE = re.compile(r"^\s*[-=*_]{3,}\s*$", re.MULTILINE)


def looks_like_markdown(text: str) -> bool:
    """Cheap heuristic to skip conversion when text is already HTML."""
    if not text:
        return False
    if "<b>" in text or "<i>" in text or "<a href" in text or "<pre>" in text:
        return False
    return bool(
        _BOLD_RE.search(text)
        or _HEADING_RE.search(text)
        or _FENCE_RE.search(text)
        or _LINK_RE.search(text)
    )


def markdown_to_telegram_html(text: str) -> str:
    """Convert common Markdown syntax to Telegram-compatible HTML."""
    if not text:
        return text

    # 1. Code fences first — protect their content from other replacements.
    placeholders: list[str] = []

    def _save_fence(m: re.Match) -> str:
        body = m.group(2).rstrip("\n")
        placeholders.append(f"<pre>{html.escape(body)}</pre>")
        return f"\x00FENCE{len(placeholders) - 1}\x00"

    text = _FENCE_RE.sub(_save_fence, text)

    # 2. Headings → bold line.
    text = _HEADING_RE.sub(lambda m: f"<b>{m.group(2)}</b>", text)

    # 3. Horizontal rules → blank line.
    text = _HR_RE.sub("", text)

    # 4. Bold (both ** and __).
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _BOLD_ALT_RE.sub(r"<b>\1</b>", text)

    # 5. Italic — apply after bold so ** isn't consumed by single-star rule.
    text = _ITALIC_STAR_RE.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", text)

    # 6. Inline code.
    text = _INLINE_CODE_RE.sub(lambda m: f"<code>{html.escape(m.group(1))}</code>", text)

    # 7. Links.
    text = _LINK_RE.sub(r'<a href="\2">\1</a>', text)

    # 8. Restore code fences.
    for i, block in enumerate(placeholders):
        text = text.replace(f"\x00FENCE{i}\x00", block)

    return text.strip()


def normalize_post_html(text: str) -> str:
    """Entry point used by AI providers — runs conversion only if needed."""
    if not text:
        return text
    if looks_like_markdown(text):
        return markdown_to_telegram_html(text)
    return text.strip()
