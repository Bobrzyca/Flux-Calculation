"""Shared text-encoding detection for the file parsers (pure; no HTTP).

Real field exports come off Windows machines in a legacy code page (**cp1250**
in Poland) or **UTF-16**, not UTF-8, and carry non-ASCII bytes (``°C``, ``ą``, a
site name like ``nad tamą``). Reading them strictly as UTF-8 raises
``UnicodeDecodeError`` and the whole file is rejected. We sniff the encoding
instead: a UTF-16 BOM wins outright, otherwise we take the first of
``utf-8-sig`` / ``cp1250`` / ``latin-1`` that decodes the file's head. ``latin-1``
decodes any byte sequence, so a readable text file always resolves to *some*
encoding — and since the columns and numbers the parsers rely on are ASCII, the
choice only affects incidental text (site names) we don't compute on.
"""

from pathlib import Path

# Tried in order for a non-UTF-16 text file. latin-1 never raises, so it's the
# guaranteed fallback.
_TEXT_ENCODINGS = ("utf-8-sig", "cp1250", "latin-1")


def detect_encoding(path: str | Path) -> str | None:
    """First encoding that decodes the file's head, or None if it can't be opened.

    A UTF-16 byte-order mark is honoured first (its bytes also decode as garbage
    under latin-1, which would otherwise win and corrupt the text).
    """
    try:
        with open(path, "rb") as f:
            head = f.read(65536)
    except OSError:
        return None
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    for encoding in _TEXT_ENCODINGS:
        try:
            head.decode(encoding)
        except UnicodeDecodeError:
            continue
        else:
            return encoding
    return None
