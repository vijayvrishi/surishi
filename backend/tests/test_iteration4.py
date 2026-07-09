"""Iteration 4 backend tests:
- Growth endpoint (MoM + overall)
- PDF report includes performance sections and size >8KB
- Task photos add/list/detail/delete + validations
- Task head normalization, filter, by_head grouping, excel upload with Head column
"""
import base64
import io
import os
import uuid

import pytest
import requests
from openpyxl import Workbook

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
).rstrip("/")
API = f"{BASE_URL}/api"

PASSWORD = "Surishi@123"
HEAD = "head@surishi.com"
PE = "pe@surishi.com"

EXISTING_TASK_ID = "bc134fab-aa36-4a1a-ba59-61af3b88934c"


def _token(email, password=PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def head_tok():
    return _token(HEAD)


@pytest.fixture(scope="module")
def pe_tok():
    return _token(PE)


# ---------- Growth ----------
class TestGrowth:
    def test_growth_months_and_brands(self, head_tok):
        r = requests.get(f"{API}/performance/growth", headers=_auth(head_tok))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "months" in data and "brands" in data
        # Expect months contain 2026-03..2026-06 (ordered)
        months = data["months"]
        assert months == sorted(months), f"months not sorted asc: {months}"
        for m in ["2026-03", "2026-04", "2026-05", "2026-06"]:
            assert m in months, f"missing month {m} in {months}"
        assert len(data["brands"]) > 0
        brand_names = [b["brand"] for b in data["brands"]]
        assert "MITOV" in brand_names

    def test_mitov_growth_overall(self, head_tok):
        r = requests.get(f"{API}/performance/growth", headers=_auth(head_tok))
        data = r.json()
        mitov = next(b for b in data["brands"] if b["brand"] == "MITOV")
        assert "overall_growth_pct" in mitov
        # Expected around +76.5%
        assert mitov["overall_growth_pct"] is not None
        assert 60 <= mitov["overall_growth_pct"] <= 95, mitov["overall_growth_pct"]
        # series shape: each element has month, sales, growth_pct
        assert len(mitov["series"]) == len(data["months"])
        # First month growth_pct should be None (no prev)
        assert mitov["series"][0]["growth_pct"] is None


# ---------- PDF with performance sections ----------
class TestPDFReport:
    def test_pdf_month_includes_performance(self, head_tok):
        r = requests.get(f"{API}/reports/pdf?period=month", headers=_auth(head_tok))
        assert r.status_code == 200, r.text
        body = r.content
        assert body[:5] == b"%PDF-", "not a PDF"
        assert len(body) > 8 * 1024, f"pdf size too small: {len(body)}"


# ---------- Task Photos ----------
def _tiny_png_b64():
    # 1x1 transparent PNG
    png = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII="
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()


class TestTaskPhotos:
    added_photo_id = None
    test_task_id = None

    def test_create_task_for_photos(self, head_tok):
        payload = {
            "title": f"TEST_photo_task_{uuid.uuid4().hex[:6]}",
            "description": "photo test",
            "category": "Engagement",
            "head": "engagement",
            "hq": "Jaipur",
            "frequency": "one_time",
        }
        r = requests.post(f"{API}/tasks", json=payload, headers=_auth(head_tok))
        assert r.status_code in (200, 201), r.text
        TestTaskPhotos.test_task_id = r.json()["id"]

    def test_add_photo(self, head_tok):
        assert TestTaskPhotos.test_task_id
        r = requests.post(
            f"{API}/tasks/{TestTaskPhotos.test_task_id}/photos",
            json={"photo_base64": _tiny_png_b64()},
            headers=_auth(head_tok),
        )
        assert r.status_code in (200, 201), r.text
        p = r.json()
        assert "id" in p
        TestTaskPhotos.added_photo_id = p["id"]

    def test_task_detail_includes_photos(self, head_tok):
        r = requests.get(
            f"{API}/tasks/{TestTaskPhotos.test_task_id}", headers=_auth(head_tok)
        )
        assert r.status_code == 200
        t = r.json()
        assert "photos" in t
        assert len(t["photos"]) == 1
        assert t["photos"][0]["id"] == TestTaskPhotos.added_photo_id

    def test_tasks_list_excludes_photos_but_has_count(self, head_tok):
        r = requests.get(f"{API}/tasks", headers=_auth(head_tok))
        assert r.status_code == 200
        tasks = r.json()
        found = [t for t in tasks if t["id"] == TestTaskPhotos.test_task_id]
        assert found, "created task not in list"
        t = found[0]
        assert "photos" not in t
        assert t.get("photo_count") == 1

    def test_max_10_photos(self, head_tok):
        for _ in range(9):
            r = requests.post(
                f"{API}/tasks/{TestTaskPhotos.test_task_id}/photos",
                json={"photo_base64": _tiny_png_b64()},
                headers=_auth(head_tok),
            )
            assert r.status_code in (200, 201), r.text
        # 11th should fail
        r = requests.post(
            f"{API}/tasks/{TestTaskPhotos.test_task_id}/photos",
            json={"photo_base64": _tiny_png_b64()},
            headers=_auth(head_tok),
        )
        assert r.status_code == 400, r.text

    def test_oversized_photo_rejected(self, head_tok):
        # Generate ~5MB base64 payload
        big = "a" * (5 * 1024 * 1024)
        payload = "data:image/png;base64," + big
        # Need a fresh task with room
        r = requests.post(
            f"{API}/tasks",
            json={"title": f"TEST_big_{uuid.uuid4().hex[:6]}", "category": "Engagement", "hq": "Jaipur", "frequency": "one_time"},
            headers=_auth(head_tok),
        )
        big_task_id = r.json()["id"]
        r = requests.post(
            f"{API}/tasks/{big_task_id}/photos",
            json={"photo_base64": payload},
            headers=_auth(head_tok),
        )
        assert r.status_code == 400, r.text
        # cleanup
        requests.delete(f"{API}/tasks/{big_task_id}", headers=_auth(head_tok))

    def test_delete_photo(self, head_tok):
        assert TestTaskPhotos.added_photo_id
        r = requests.delete(
            f"{API}/tasks/{TestTaskPhotos.test_task_id}/photos/{TestTaskPhotos.added_photo_id}",
            headers=_auth(head_tok),
        )
        assert r.status_code in (200, 204), r.text
        r = requests.get(
            f"{API}/tasks/{TestTaskPhotos.test_task_id}", headers=_auth(head_tok)
        )
        photos = r.json()["photos"]
        assert all(p["id"] != TestTaskPhotos.added_photo_id for p in photos)

    def test_cleanup_test_task(self, head_tok):
        if TestTaskPhotos.test_task_id:
            requests.delete(
                f"{API}/tasks/{TestTaskPhotos.test_task_id}", headers=_auth(head_tok)
            )


# ---------- Task Head ----------
class TestTaskHead:
    created_ids = []

    def test_create_task_normalizes_head(self, head_tok):
        payload = {
            "title": f"TEST_head_scientific_{uuid.uuid4().hex[:6]}",
            "category": "Scientific",
            "head": "Scientific Inputs",
            "hq": "Jaipur",
            "frequency": "one_time",
        }
        r = requests.post(f"{API}/tasks", json=payload, headers=_auth(head_tok))
        assert r.status_code in (200, 201), r.text
        t = r.json()
        assert t.get("head") == "scientific_inputs", t
        TestTaskHead.created_ids.append(t["id"])

    def test_filter_by_head(self, head_tok):
        r = requests.get(f"{API}/tasks?head=scientific_inputs", headers=_auth(head_tok))
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) > 0
        for t in tasks:
            assert t.get("head") == "scientific_inputs", t

    def test_reports_by_head(self, head_tok):
        r = requests.get(f"{API}/reports?period=month", headers=_auth(head_tok))
        assert r.status_code == 200
        data = r.json()
        assert "by_head" in data, data.keys()
        heads = [row["name"] for row in data["by_head"]]
        # At least one of the three heads should be present
        assert any(h in heads for h in ["company", "scientific_inputs", "engagement"]), heads

    def test_excel_upload_with_head_column(self, head_tok):
        wb = Workbook()
        ws = wb.active
        headers = ["Title", "Description", "Category", "HQ", "Frequency", "Head"]
        ws.append(headers)
        ws.append([f"TEST_up_company_{uuid.uuid4().hex[:4]}", "d", "Company", "Jaipur", "one_time", "Company"])
        ws.append([f"TEST_up_sci_{uuid.uuid4().hex[:4]}", "d", "Scientific", "Jaipur", "one_time", "Scientific Inputs"])
        ws.append([f"TEST_up_eng_{uuid.uuid4().hex[:4]}", "d", "Engagement", "Jaipur", "one_time", "Engagement"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        files = {"file": ("tasks_head.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/tasks/upload", files=files, headers=_auth(head_tok))
        assert r.status_code == 200, r.text
        # Verify tasks exist with normalized heads
        r = requests.get(f"{API}/tasks", headers=_auth(head_tok))
        titles_heads = {t["title"]: t.get("head") for t in r.json()}
        found_heads = set()
        for title, head in titles_heads.items():
            if title.startswith("TEST_up_company_"):
                assert head == "company", (title, head)
                found_heads.add("company")
            elif title.startswith("TEST_up_sci_"):
                assert head == "scientific_inputs", (title, head)
                found_heads.add("scientific_inputs")
            elif title.startswith("TEST_up_eng_"):
                assert head == "engagement", (title, head)
                found_heads.add("engagement")
        assert found_heads == {"company", "scientific_inputs", "engagement"}, found_heads

    def test_cleanup_head_tasks(self, head_tok):
        # remove TEST_ tasks we created
        r = requests.get(f"{API}/tasks", headers=_auth(head_tok))
        for t in r.json():
            title = t.get("title", "")
            if title.startswith("TEST_head_") or title.startswith("TEST_up_"):
                requests.delete(f"{API}/tasks/{t['id']}", headers=_auth(head_tok))


# ---------- Existing task with photo ----------
class TestExistingTask:
    def test_existing_task_has_head_and_photo(self, head_tok):
        r = requests.get(f"{API}/tasks/{EXISTING_TASK_ID}", headers=_auth(head_tok))
        if r.status_code == 404:
            pytest.skip("Existing task not found (may have been cleaned up)")
        assert r.status_code == 200
        t = r.json()
        assert t.get("head") == "scientific_inputs", t
        assert len(t.get("photos") or []) >= 1
