from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass


class ModerationVerdict(str, enum.Enum):
    OK = "ok"
    FLAG = "flag"
    BLOCK = "block"


@dataclass
class ModerationResult:
    verdict: ModerationVerdict
    reason: str = ""
    categories: list[str] | None = None

    @property
    def passed(self) -> bool:
        return self.verdict == ModerationVerdict.OK


class AIProvider(ABC):
    name: str = "base"

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    async def generate_post(self, topic: str, channel_context: str) -> str: ...

    @abstractmethod
    async def improve_post(self, text: str) -> str: ...

    @abstractmethod
    async def check_content(self, text: str) -> ModerationResult: ...


GENERATION_SYSTEM = (
    "You are an expert content writer for a Telegram channel. Write engaging, "
    "concise posts in the channel's voice. Output only the post text — no preamble.\n\n"
    "FORMATTING — use Telegram HTML, never Markdown:\n"
    "• Bold: <b>text</b>   (NEVER **text**)\n"
    "• Italic: <i>text</i> (NEVER *text* or _text_)\n"
    "• Underline: <u>text</u>\n"
    "• Strikethrough: <s>text</s>\n"
    "• Inline code: <code>text</code>\n"
    "• Code block: <pre>text</pre>\n"
    "• Link: <a href=\"https://example.com\">text</a>\n"
    "• Line breaks: real newlines, not <br>.\n"
    "• Do NOT wrap output in <html>/<body> or code fences.\n"
    "• Telegram does NOT support headings (#), tables, or nested lists — use bold "
    "for section titles and plain bullet lines (•, –, or numbers)."
)

MODERATION_SYSTEM = (
    "You are a content moderator. Given a post for a public channel, decide if it is "
    "safe to publish. Reply with strict JSON: "
    '{"verdict": "ok|flag|block", "reason": "...", "categories": ["spam", "scam", "hate", "nsfw", ...]}. '
    "Use 'block' for spam, scams, hate speech, NSFW, illegal content. "
    "Use 'flag' for borderline content that needs human review. "
    "Use 'ok' otherwise."
)
