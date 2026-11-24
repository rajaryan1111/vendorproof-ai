"""Scan the tracked release tree without emitting matched contents."""

import re
import subprocess
from pathlib import Path


def main():
    keys = re.compile(
        rb"(?:AKIA|ASIA)[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{32,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AGE-SECRET-KEY-1[A-Z0-9]{50,}"
    )
    paths = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    for raw in filter(None, paths):
        path = Path(raw.decode())
        if (
            path.name == ".env"
            or path.suffix in {".pdf", ".dump", ".age", ".pem", ".key"}
            or keys.search(path.read_bytes())
        ):
            raise SystemExit(f"Inspect tracked path {path}")
    print("Tracked file and credential signature checks passed.")


if __name__ == "__main__":
    main()
