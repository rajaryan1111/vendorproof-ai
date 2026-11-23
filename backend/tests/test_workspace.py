import io

from pypdf import PdfWriter


def sample_pdf():
    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(72, 72)
    writer.write(buf)
    return buf.getvalue()


def test_workspace(accounts):
    admin, operator, reviewer, auditor, outside = (
        accounts[k] for k in ["admin", "operator", "reviewer", "auditor", "outside"]
    )
    root = "/api/v1/suppliers"
    assert admin.get("/api/v1/health/db").status_code == 200
    assert operator.post(root, json={"name": "  "}).status_code == 422
    row = operator.post(root, json={"name": "Synthetic one"}).json()
    path = root + "/" + row["id"]
    assert reviewer.get(path).status_code == 200
    for client in (reviewer, auditor):
        assert client.post(root, json={"name": "denied"}).status_code == 403
    assert outside.get(path).status_code == 404
    assert outside.patch(path, json={"name": "denied"}).status_code == 404
    assert outside.get(root).json() == []
    assert admin.patch(path, json={"name": "Updated one"}).status_code == 200
    assert len(admin.get(root + "?q=Updated").json()) == 1
    assert admin.get(root + "?page=2").json() == []
    docs = path + "/documents"
    pdf = sample_pdf()
    headers = {"content-type": "application/pdf", "x-filename": "supplier.pdf"}
    assert operator.post(docs, content=b"x", headers=headers).status_code == 415
    assert (
        operator.post(docs, content=b"%PDF-bad%%EOF", headers=headers).status_code
        == 422
    )
    assert (
        operator.post(
            docs, content=pdf, headers={**headers, "x-filename": "../escape.pdf"}
        ).status_code
        == 415
    )
    assert (
        operator.post(
            docs, content=pdf, headers={**headers, "content-type": "text/plain"}
        ).status_code
        == 415
    )
    assert (
        operator.post(
            docs, content=b"0" * (5 * 1024 * 1024 + 1), headers=headers
        ).status_code
        == 413
    )
    assert outside.post(docs, content=pdf, headers=headers).status_code == 404
    key = operator.post(docs, content=pdf, headers=headers).json()["id"]
    assert outside.get(docs + "/" + key).status_code == 404
    assert auditor.get(docs + "/" + key).status_code == 403
    assert admin.get(docs + "/" + key).content == pdf
    replacement = operator.post(
        docs + "?replaces=" + key, content=pdf, headers=headers
    ).json()["id"]
    assert admin.get(docs + "/" + key).status_code == 404
    assert admin.delete(docs + "/" + replacement).status_code == 200
    assert operator.delete(path).status_code == 403
    assert (
        admin.delete(path, headers={"Origin": "https://other.invalid"}).status_code
        == 403
    )
    assert admin.delete(path).status_code == 200
    assert admin.get(root + "?archived=true").json()[0]["archived"]
    assert admin.get("/api/v1/dashboard").json()["archived"] == 1
    old_cookie = admin.cookies.get("vp_session")
    assert admin.post("/api/v1/logout").status_code == 200
    assert admin.get(path).status_code == 401
    admin.cookies.set("vp_session", old_cookie)
    assert admin.get(path).status_code == 401
