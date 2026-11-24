"""Launch protocol for document parsers. Production requires Linux user namespaces."""

import os
import sys
from pathlib import Path


def command(module, settings, *args):
    python = [sys.executable, "-m", module, *args]
    if settings.environment != "production":
        return python
    app = Path(__file__).resolve().parents[2] / "app"
    venv = Path(sys.prefix)
    cmd = [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--cap-drop",
        "ALL",
        "--ro-bind",
        "/usr",
        "/usr",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
    ]
    for name in ("/bin", "/lib", "/lib64"):
        if os.path.exists(name):
            cmd += ["--ro-bind", name, name]
    return [
        *cmd,
        "--ro-bind",
        str(venv),
        str(venv),
        "--ro-bind",
        str(app),
        "/work/app",
        "--chdir",
        "/work",
        "--",
        *python,
    ]
