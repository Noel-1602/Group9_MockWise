"""Text cleaning and normalization pipeline for extracted resume content."""

import re
from typing import Optional
import unicodedata


# Common bullet point glyphs used in resumes
BULLET_CHARS = r"[\u00B7\u2022\u2023\u25E6\u2043\u2219\u25CF\u25CB\u25AA\u25AB\u2013\u2014\*]"

# Regex to detect page number headers/footers like "Page 1 of 2" or "Page 1"
PAGE_NUMBER_PATTERN = re.compile(
    r"^\s*(?:page\s*\d+\s*(?:of\s*\d+)?|\d+\s*/\s*\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def remove_control_characters(text: str) -> str:
    """Remove non-printable control characters while preserving standard whitespace."""
    if not text:
        return ""
    # Keep standard tab, newline, carriage return, and printable characters
    return "".join(
        ch for ch in text
        if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\r", "\t")
    )


def normalize_bullets(text: str) -> str:
    """Standardize disparate unicode bullet points into consistent markdown-style dashes."""
    if not text:
        return ""
    # Replace bullet chars at the start of lines or preceded by whitespace with standard '- '
    return re.sub(rf"(?:^|\n)\s*{BULLET_CHARS}\s*", r"\n- ", text)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace, tabs, and line breaks."""
    if not text:
        return ""

    # Normalize carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Replace non-breaking and special unicode spaces with regular space
    text = re.sub(r"[\u00A0\u1680\u180E\u2000-\u200B\u202F\u205F\u3000\uFEFF]", " ", text)

    # Collapse multiple inline spaces and tabs into a single space
    lines = []
    for line in text.split("\n"):
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned_line)

    cleaned_text = "\n".join(lines)

    # Collapse 3 or more consecutive newlines into 2
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return cleaned_text.strip()


def remove_headers_and_footers(text: str) -> str:
    """Strip recurring page numbers and common artifacts."""
    if not text:
        return ""
    return PAGE_NUMBER_PATTERN.sub("", text)


def clean_text(raw_text: Optional[str]) -> str:
    """Run the complete cleaning and normalization pipeline on extracted text.

    Args:
        raw_text: Raw extracted string from file.

    Returns:
        Cleaned, normalized string ready for LLM structuring.
    """
    if not raw_text or not raw_text.strip():
        return ""

    text = remove_control_characters(raw_text)
    text = remove_headers_and_footers(text)
    text = normalize_bullets(text)
    text = normalize_whitespace(text)

    return text


def clean_resume_text(raw_text: str) -> str:
    """Lightly normalise raw extracted resume text with regex-only rules.

    Rules applied (in order):
    1. Collapse runs of 3 or more consecutive newlines down to exactly 2.
    2. Collapse runs of 2 or more spaces or tabs on a single line down to 1.
    3. Strip leading and trailing whitespace from the whole string.

    No bullet normalisation, no unicode replacement, and no page-header
    removal are performed — those belong in the heavier ``clean_text``
    pipeline.  This function is deliberately minimal so it can be used as
    a first-pass step without side-effects.

    Args:
        raw_text: Raw string returned by an extraction function.

    Returns:
        Cleaned string, or ``""`` if the input is empty.
    """
    if not raw_text:
        return ""

    # 1. Collapse 3+ consecutive newlines → 2 newlines
    text = re.sub(r"\n{3,}", "\n\n", raw_text)

    # 2. Collapse 2+ spaces/tabs on the same line → 1 space
    #    Use a character class that matches spaces and tabs but NOT newlines.
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 3. Strip leading/trailing whitespace from the whole string
    return text.strip()

