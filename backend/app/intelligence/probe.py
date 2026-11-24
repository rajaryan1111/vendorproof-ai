"""Production startup check executed inside the parser namespace."""

import os
import shutil
import sys

if __name__ == "__main__":
    if (
        os.geteuid() == 0
        or os.path.exists("/etc/vendorproof")
        or not shutil.which("tesseract")
    ):
        sys.exit(1)
    import pymupdf
    from pypdf import PdfReader

    if pymupdf.Document and PdfReader:
        print("parser-ready")
