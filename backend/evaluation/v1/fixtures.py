import random

import pymupdf


def make_pdf(case):
    with pymupdf.open() as output:
        for n, (text, medium) in enumerate(
            zip(case["pages"], case["media"], strict=True)
        ):
            with pymupdf.open() as draft:
                page = draft.new_page(width=540, height=720)
                if medium != "blank":
                    page.insert_text((36, 56), text, fontsize=14)
                if medium in {"scan", "degraded"}:
                    scale = 2 if medium == "scan" else 0.72
                    if medium == "degraded":
                        rng = random.Random(42 + n)
                        for _ in range(100):
                            x, y = rng.randrange(30, 340), rng.randrange(40, 110)
                            page.draw_line(
                                (x, y), (x + 2, y + 1), color=(0.5, 0.5, 0.5)
                            )
                    image = page.get_pixmap(
                        matrix=pymupdf.Matrix(scale, scale)
                    ).tobytes("png")
                    out = output.new_page(width=540, height=720)
                    out.insert_image(out.rect, stream=image)
                else:
                    if medium == "mixed":
                        image = page.get_pixmap().tobytes("png")
                        page.insert_image(pymupdf.Rect(36, 250, 176, 430), stream=image)
                    output.insert_pdf(draft)
        return output.tobytes()
