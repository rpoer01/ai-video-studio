from __future__ import annotations

import re
from typing import Iterable

try:
    from pythainlp.tokenize import word_tokenize
except Exception:  # pragma: no cover - runtime fallback when pythainlp is unavailable
    word_tokenize = None


THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
LATIN_RE = re.compile(r"[A-Za-z]")


def language_of(text: str) -> str:
    if THAI_RE.search(text):
        return "th"
    if LATIN_RE.search(text):
        return "en"
    return "other"


def _split_mixed_text(text: str) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    current_lang = ""
    current = []
    for char in text:
        lang = language_of(char)
        if lang == "other" and current_lang:
            current.append(char)
            continue
        if current and lang != current_lang and lang != "other":
            parts.append((current_lang, "".join(current).strip()))
            current = []
        current_lang = lang if lang != "other" else current_lang or "other"
        current.append(char)
    if current:
        parts.append((current_lang, "".join(current).strip()))
    return [(lang, part) for lang, part in parts if part]


def _thai_tokens(text: str) -> list[str]:
    if word_tokenize is None:
        return [text]
    tokens = [token.strip() for token in word_tokenize(text, engine="newmm") if token.strip()]
    return tokens or [text]


def _tokens_for_word(word: dict) -> list[dict]:
    text = str(word.get("word") or word.get("text") or "").strip()
    if not text:
        return []

    start = float(word.get("start", 0.0))
    end = max(start + 0.03, float(word.get("end", start + 0.03)))
    pieces: list[tuple[str, str]] = []
    for lang, part in _split_mixed_text(text):
        if lang == "th":
            pieces.extend(("th", token) for token in _thai_tokens(part))
        elif lang == "en":
            pieces.extend(("en", token) for token in re.findall(r"[A-Za-z0-9']+|[^\sA-Za-z0-9]", part))
        else:
            pieces.append((lang, part))

    pieces = [(lang, token) for lang, token in pieces if token.strip()]
    if not pieces:
        return []

    span = (end - start) / len(pieces)
    tokens = []
    for index, (lang, token) in enumerate(pieces):
        token_start = start + span * index
        token_end = end if index == len(pieces) - 1 else start + span * (index + 1)
        tokens.append({"word": token, "start": token_start, "end": token_end, "lang": lang})
    return tokens


def normalize_words(words: Iterable[dict]) -> list[dict]:
    normalized: list[dict] = []
    for word in words:
        normalized.extend(_tokens_for_word(word))
    return normalized


def join_tokens(tokens: list[dict]) -> str:
    output = ""
    previous_lang = ""
    for token in tokens:
        text = str(token.get("word", "")).strip()
        lang = token.get("lang") or language_of(text)
        if not text:
            continue
        if not output:
            output = text
        elif previous_lang == "th" and lang == "th":
            output += text
        else:
            output += " " + text
        previous_lang = lang
    return output


def segment_words(words: Iterable[dict], max_words: int = 5, max_gap: float = 0.45) -> list[list[dict]]:
    tokens = normalize_words(words)
    chunks: list[list[dict]] = []
    current: list[dict] = []

    for token in tokens:
        lang = token.get("lang") or language_of(str(token.get("word", "")))
        gap = 0.0
        if current:
            gap = float(token["start"]) - float(current[-1]["end"])
        current_lang = current[-1].get("lang") if current else lang
        language_changed = current and lang in {"th", "en"} and current_lang in {"th", "en"} and lang != current_lang
        too_long = current and len(current) >= max_words
        too_far = current and gap > max_gap

        if current and (language_changed or too_long or too_far):
            chunks.append(current)
            current = []
        current.append(token)

    if current:
        chunks.append(current)
    return chunks
