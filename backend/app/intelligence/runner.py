"""Private child process protocol. No application settings, database or network provider."""

import hashlib
import json
import resource
import sys
from uuid import UUID

from .extract import build_report
from .pages import ProcessingError, read_pages


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    if sys.platform.startswith("linux"):
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    data = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    key, digest, language = sys.argv[1:]
    if hashlib.sha256(data).hexdigest() != digest:
        raise ProcessingError("version_mismatch")
    pages = read_pages(data, language)
    print(build_report(UUID(key), digest, pages).model_dump_json())


if __name__ == "__main__":
    try:
        main()
    except ProcessingError as exc:
        print(json.dumps({"error": str(exc)}))
