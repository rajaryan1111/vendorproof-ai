import csv
import io
import re
import subprocess

import pymupdf

from .schema import Page, Segment


class ProcessingError(Exception):
    """Only stable codes may cross the worker boundary."""


def ocr(page, language, clip=None):
    if not re.fullmatch("[a-zA-Z_]{2,24}(?:[+][a-zA-Z_]{2,24}){0,2}", language):
        raise ProcessingError("ocr_language_invalid")
    scale = min(2.5, 2200 / max(page.rect.width, page.rect.height, 1))
    pix = page.get_pixmap(
        clip=clip,
        matrix=pymupdf.Matrix(scale, scale),
        colorspace=pymupdf.csGRAY,
        alpha=False,
    )
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", language, "--psm", "6", "tsv"],
            input=pix.tobytes("png"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        )
    except FileNotFoundError:
        raise ProcessingError("ocr_unavailable") from None
    except subprocess.TimeoutExpired:
        raise ProcessingError("ocr_timeout") from None
    except subprocess.CalledProcessError:
        raise ProcessingError("ocr_failed") from None
    groups = {}
    for r in csv.DictReader(
        io.StringIO(result.stdout.decode()), delimiter="\t", quoting=csv.QUOTE_NONE
    ):
        if r["level"] == "5" and r["text"].strip():
            groups.setdefault((r["block_num"], r["par_num"], r["line_num"]), []).append(
                r
            )
    lines = []
    for words in groups.values():
        boxes = [
            (int(w["left"]), int(w["top"]), int(w["width"]), int(w["height"]))
            for w in words
        ]
        bbox = (
            (pix.x + min(b[0] for b in boxes)) / scale,
            (pix.y + min(b[1] for b in boxes)) / scale,
            (pix.x + max(b[0] + b[2] for b in boxes)) / scale,
            (pix.y + max(b[1] + b[3] for b in boxes)) / scale,
        )
        lines.append(
            Segment(
                text=" ".join(w["text"] for w in words),
                method="ocr",
                bbox=bbox,
                confidence=sum(float(w["conf"]) for w in words) / len(words),
            )
        )
    return lines


def read_pages(data, language):
    pages = []
    total = 0
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass or not 1 <= len(pdf) <= 40:
                raise ProcessingError("unsupported_pdf")
            for number, page in enumerate(pdf, 1):
                text = page.get_text(sort=True).strip()
                segments = [Segment(method="native", text=text)] if text else []
                warning = None
                if sum(ch.isalnum() for ch in text) < 12 or text.count("\ufffd") > max(
                    1, len(text) // 10
                ):
                    extra = ocr(page, language)
                    segments += extra
                    if not extra:
                        warning = "unreadable_page" if not text else "sparse_text"
                elif images := page.get_image_info():
                    # Preserve searchable text. OCR substantial image regions only.
                    regions = [
                        pymupdf.Rect(im["bbox"]) * page.rotation_matrix & page.rect
                        for im in images
                    ]
                    substantial = [
                        box
                        for box in regions
                        if box.get_area() > 0.12 * page.rect.get_area()
                    ]
                    if len(substantial) > 4:
                        warning = "image_region_limit"
                    elif not substantial:
                        warning = "mixed_page_native_only"
                    for box in substantial[:4]:
                        lines = ocr(page, language, box)
                        segments.extend(lines)
                        if not lines:
                            warning = "unreadable_image_region"
                words = sum(len(s.text.split()) for s in segments)
                chars = sum(len(s.text) for s in segments)
                total += chars
                if total > 200000:
                    raise ProcessingError("text_limit")
                pages.append(
                    Page(
                        number=number,
                        segments=segments,
                        characters=chars,
                        words=words,
                        warning=warning,
                    )
                )
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError("pdf_read_failed") from exc
    return pages
