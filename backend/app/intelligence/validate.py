"""Bounded PDF intake parser; stdout contains only a status code."""

import io
import resource
import sys

from pypdf import PdfReader


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    if sys.platform.startswith("linux"):
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    try:
        data = sys.stdin.buffer.read(5 * 1024**2 + 1)
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 40:
            return 1
    except Exception:  # noqa: BLE001 - malformed parser input returns one bounded outcome.
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
