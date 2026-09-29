"""Output helpers for scripts that run with credentials in the environment.

Every line a script prints goes through ``say``, which masks the value of any
environment variable that looks like a secret. Belt and braces: the scripts never
print tokens on purpose, and this catches the accidental case (an exception message
that echoes a header, say).
"""

from __future__ import annotations

import os
import re
import sys

_SECRET_NAME = re.compile(r"(TOKEN|SECRET|PASSWORD|API_KEY|ACCESS_KEY|PRIVATE_KEY)", re.I)
MASK = "[redacted]"


def secret_values(environ: dict[str, str] | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    values = {v for k, v in env.items() if _SECRET_NAME.search(k) and len(v) >= 8}
    return sorted(values, key=len, reverse=True)


def mask(text: str, secrets: list[str] | None = None) -> str:
    for value in secret_values() if secrets is None else secrets:
        text = text.replace(value, MASK)
    return text


def say(*parts: object) -> None:
    print(mask(" ".join(str(p) for p in parts)), flush=True)


def fail(*parts: object) -> None:
    print(mask(" ".join(str(p) for p in parts)), file=sys.stderr, flush=True)
