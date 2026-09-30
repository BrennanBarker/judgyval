"""Apply model-proposed search/replace edits to a text, with strict validation.

Each edit's `original` must match exactly one location in the text, and edits
may not overlap. Failures raise `EditError` with a message suitable for feeding
back to the model on retry.
"""

from dataclasses import dataclass
from typing import Protocol, Sequence


class EditLike(Protocol):
    original: str
    replacement: str


class EditError(ValueError):
    pass


@dataclass(frozen=True)
class Hunk:
    """One applied edit, located by character offsets in the original text."""

    start: int
    end: int
    original: str
    replacement: str


@dataclass(frozen=True)
class AppliedEdits:
    text: str
    hunks: list[Hunk]


_CHAR_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
}


def _normalize(text: str) -> tuple[str, list[int]]:
    """Map curly quotes/dashes to ASCII and collapse whitespace runs.

    Returns the normalized text and, for each normalized character, its index
    in the input text.
    """
    chars: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        ch = _CHAR_MAP.get(ch, ch)
        if ch.isspace():
            if chars and chars[-1] == " ":
                continue
            ch = " "
        chars.append(ch)
        index.append(i)
    return "".join(chars), index


def _find_all(haystack: str, needle: str) -> list[int]:
    starts, i = [], haystack.find(needle)
    while i != -1:
        starts.append(i)
        i = haystack.find(needle, i + 1)
    return starts


def _locate(text: str, original: str, lenient: bool) -> tuple[int, int]:
    starts = _find_all(text, original)
    if len(starts) == 1:
        return starts[0], starts[0] + len(original)
    if len(starts) > 1:
        raise EditError(
            f"`original` {original!r} appears {len(starts)} times; "
            "include more surrounding context so it matches exactly once."
        )
    if lenient:
        norm_text, index = _normalize(text)
        norm_original = _normalize(original)[0].strip()
        norm_starts = _find_all(norm_text, norm_original) if norm_original else []
        if len(norm_starts) == 1:
            s = norm_starts[0]
            return index[s], index[s + len(norm_original) - 1] + 1
        if len(norm_starts) > 1:
            raise EditError(
                f"`original` {original!r} appears {len(norm_starts)} times; "
                "include more surrounding context so it matches exactly once."
            )
    raise EditError(
        f"`original` {original!r} was not found; copy it verbatim from the input."
    )


def apply_edits(
    text: str, edits: Sequence[EditLike], *, lenient: bool = False
) -> AppliedEdits:
    """Apply `edits` to `text`, returning the new text and the applied hunks.

    With `lenient=True`, an `original` that doesn't match exactly is retried
    after normalizing quotes, dashes, and whitespace on both sides.
    """
    if not edits:
        raise EditError("No edits were provided.")

    hunks = []
    for edit in edits:
        if not edit.original:
            raise EditError("An edit has an empty `original`.")
        if edit.original == edit.replacement:
            raise EditError(f"Edit for {edit.original!r} doesn't change anything.")
        start, end = _locate(text, edit.original, lenient)
        hunks.append(Hunk(start, end, text[start:end], edit.replacement))

    hunks.sort(key=lambda h: h.start)
    for prev, cur in zip(hunks, hunks[1:]):
        if cur.start < prev.end:
            raise EditError(
                f"Edits for {prev.original!r} and {cur.original!r} overlap; "
                "merge them into one edit."
            )

    pieces, pos = [], 0
    for h in hunks:
        pieces += [text[pos : h.start], h.replacement]
        pos = h.end
    pieces.append(text[pos:])
    return AppliedEdits("".join(pieces), hunks)
