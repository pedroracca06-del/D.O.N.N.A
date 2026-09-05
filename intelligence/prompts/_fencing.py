"""intelligence/prompts/_fencing.py — keep untrusted text inside its fence.

Every V1 prompt separates trusted instructions from untrusted content with
`=== NAME ===` marker lines. Interpolating raw text between them lets that text
write a marker of its own and appear to close its section and open a trusted
one. Neutralising the marker inside untrusted values is what makes the fence a
boundary rather than a convention.
"""
from __future__ import annotations

import re

# Any line that looks like one of our section markers.
_MARKER = re.compile(r'^\s*={2,}.*?={2,}\s*$', re.MULTILINE)
# A run of equals signs anywhere, which is all a forged marker needs.
_RUN = re.compile(r'={2,}')


def fence(value) -> str:
    """Return `value` as text that cannot terminate or forge a section marker."""
    text = '' if value is None else str(value)
    text = _MARKER.sub(lambda m: m.group(0).replace('=', '\u2550'), text)
    return _RUN.sub(lambda m: '\u2550' * len(m.group(0)), text)


def fence_inline(value, limit: int = 64) -> str:
    """Fence a value that is interpolated INTO a marker line.

    A marker is one line. An untrusted value placed inside one can split it
    with a newline even after its equals signs are neutralised, so a value used
    there is collapsed to a single bounded line as well.
    """
    text = " ".join(fence(value).split())
    return text[:limit]
