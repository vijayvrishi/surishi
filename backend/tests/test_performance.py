"""Backend tests for iteration 3: Performance module.
- POST /api/performance/upload (auto-detect brand/territory/management, RBAC, unrecognized 400)
- Re-upload idempotency
- GET /api/performance/months
- GET /api/performance/brands|territories|management
"""
import io
import os

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

BRAND_XLSX = "/tmp/brand.xlsx"
TERR_XLSX = "/tmp/territory.xlsx"
MGMT_XLSX = "/tmp/mgmt.xlsx"


def _token(email, password=PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _upload(path, tok):
    with open(path, "rb") as f:
        return requests.post(
            f"{API}/performance/upload",
            headers=_auth(tok),
            files={"file": (os.path.basename(path), f,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )


# =========================================================
# Upload — auto detection + RBAC
# =========================================================
class TestPerformanceUpload:
    def test_admin_upload_brand(self):
        tok = _token(HEAD)
        r = _upload(BRAND_XLSX, tok)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "brand"
        assert set(["2026-03", "2026-04", "2026-05", "2026-06"]).issubset(set(data["months"]))
        assert data["inserted_count"] >= 40

    def test_admin_upload_territory(self):
        tok = _token(HEAD)
        r = _upload(TERR_XLSX, tok)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "territory"
        assert "2026-06" in data["months"]
        assert data["inserted_count"] >= 50

    def test_admin_upload_management(self):
        tok = _token(HEAD)
        r = _upload(MGMT_XLSX, tok)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "management"
        assert set(["2026-03", "2026-04", "2026-05", "2026-06"]).issubset(set(data["months"]))

    def test_non_admin_forbidden(self):
        tok = _token(PE)
        r = _upload(BRAND_XLSX, tok)
        assert r.status_code == 403, r.text

    def test_unrecognized_xlsx_returns_400(self):
        tok = _token(HEAD)
        wb = Workbook()
        ws = wb.active
        ws.title = "Random"
        ws.append(["foo", "bar", "baz"])
        ws.append([1, 2, 3])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        r = requests.post(
            f"{API}/performance/upload",
            headers=_auth(tok),
            files={"file": ("noise.xlsx", buf,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 400, r.text


# =========================================================
# Re-upload idempotency (brand)
# =========================================================
class TestBrandReuploadIdempotent:
    def test_reupload_does_not_duplicate(self):
        tok = _token(HEAD)
        # first upload done in previous test class, but re-run here to be self-contained
        _upload(BRAND_XLSX, tok)
        _upload(BRAND_XLSX, tok)
        r = requests.get(f"{API}/performance/brands", headers=_auth(tok),
                         params={"month": "2026-06"})
        assert r.status_code == 200
        data = r.json()
        assert data["month"] == "2026-06"
        assert len(data["items"]) == 11, f"expected 11 brands got {len(data['items'])}"


# =========================================================
# Months endpoint
# =========================================================
class TestPerformanceMonths:
    def test_months_lists(self):
        tok = _token(PE)
        r = requests.get(f"{API}/performance/months", headers=_auth(tok))
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["brand", "territory", "management", "all"]:
            assert k in data
        for month in ["2026-03", "2026-04", "2026-05", "2026-06"]:
            assert month in data["all"], f"missing {month} in {data['all']}"
        # newest first
        assert data["all"] == sorted(data["all"], reverse=True)


# =========================================================
# Brand / Territory / Management reads
# =========================================================
class TestPerformanceReads:
    def test_brands_jun_top_is_mitov(self):
        tok = _token(PE)
        r = requests.get(f"{API}/performance/brands", headers=_auth(tok),
                         params={"month": "2026-06"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["month"] == "2026-06"
        assert len(data["items"]) == 11
        top = data["items"][0]
        assert "MITOV" in (top.get("brand") or "").upper(), f"top brand is {top.get('brand')!r}"
        # sanity: weekly + growth fields present
        assert "sales_total" in top
        # W1..W4 exposed as either weeks array or w1..w4; verify at least one flavour
        has_weeks = "weeks" in top or all(k in top for k in ("w1", "w2", "w3", "w4"))
        assert has_weeks, f"brand doc missing weekly data: keys={list(top.keys())}"

    def test_territories_jun_regions_have_totals(self):
        tok = _token(PE)
        r = requests.get(f"{API}/performance/territories", headers=_auth(tok),
                         params={"month": "2026-06"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["month"] == "2026-06"
        assert isinstance(data["regions"], list)
        assert len(data["regions"]) >= 1
        first = data["regions"][0]
        for k in ["region", "items", "target_total", "sales_total"]:
            assert k in first, f"missing {k}"
        # BE/KAM name field present on items
        assert len(first["items"]) >= 1
        row = first["items"][0]
        # HQ + at least one of the identifying name fields
        assert "hq" in row or "HQ" in row

    def test_management_jun_metrics(self):
        tok = _token(PE)
        r = requests.get(f"{API}/performance/management", headers=_auth(tok),
                         params={"month": "2026-06"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["month"] == "2026-06"
        assert data["metrics"] is not None, "metrics should not be None for 2026-06"

    def test_default_month_is_latest(self):
        tok = _token(PE)
        r = requests.get(f"{API}/performance/brands", headers=_auth(tok))
        assert r.status_code == 200
        assert r.json()["month"] == "2026-06"


# =========================================================
# Regression: task upload still works
# =========================================================
class TestTaskUploadRegression:
    def test_task_upload_still_works(self):
        tok = _token(HEAD)
        wb = Workbook()
        ws = wb.active
        ws.append([
            "Task Name", "Description", "Assignee", "Role", "HQ", "Frequency",
            "Start Date", "Due Date", "Category", "Target Amount", "Reporting Due Date",
        ])
        ws.append([
            "TEST Perf Regression Task", "regression", "Ravi", "product_executive",
            "Mumbai", "Daily", "2026-07-01", "2026-07-15", "Task", None, "2026-07-16",
        ])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        r = requests.post(
            f"{API}/tasks/upload",
            headers=_auth(tok),
            files={"file": ("regr.xlsx", buf,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("inserted_count", 0) >= 1
