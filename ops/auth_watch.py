"""Summarize recent API authentication failures without forwarding request data."""

import json
import subprocess


def main():
    failed = 0
    with subprocess.Popen(
        [
            "journalctl",
            "--no-pager",
            "--quiet",
            "-u",
            "vendorproof-api.service",
            "--since",
            "5 minutes ago",
            "-o",
            "cat",
        ],
        stdout=subprocess.PIPE,
        text=True,
    ) as journal:
        for line in journal.stdout:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if (
                isinstance(record, dict)
                and record.get("operation") == "POST /api/v1/login"
                and record.get("status") in (401, 429)
            ):
                failed += 1
        if journal.wait():
            raise SystemExit("API journal unavailable")
    print(
        json.dumps(
            {"event": "authentication_window", "seconds": 300, "failures": failed}
        )
    )
    return int(failed >= 20)


if __name__ == "__main__":
    raise SystemExit(main())
