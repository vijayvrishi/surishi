"""Backend API tests for Surishi Pharma Marketing Execution app."""
import io
import os
import pytest
import requests
from openpyxl import Workbook

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "https://pharma-task-tracker.preview.emergentagent.com"
).rstrip("/")

API = f"{BASE_URL}/api"
ADMIN_EMAIL = "head@surishi.com"
NON_ADMIN_EMAIL = "pe@surishi.com"
PASSWORD = "Surishi@123"


# ------------- fixtures -------------
@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(http):
    r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def user_token(http):
    r = http.post(f"{API}/auth/login", json={"email": NON_ADMIN_EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ------------- auth -------------
class TestAuth:
    def test_login_admin_returns_token_and_user(self, http):
        r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and data["access_token"]
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "marketing_head"

    def test_login_invalid_credentials(self, http):
        r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_register_new_user_with_role(self, http):
        import uuid as _u
        email = f"test_{_u.uuid4().hex[:8]}@surishi.com"
        r = http.post(f"{API}/auth/register", json={
            "name": "TEST User", "email": email, "password": "test1234",
            "role": "product_executive", "hq": "Mumbai"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == email.lower()
        assert data["user"]["role"] == "product_executive"
        assert data["access_token"]

    def test_register_invalid_role(self, http):
        import uuid as _u
        email = f"TEST_{_u.uuid4().hex[:8]}@surishi.com"
        r = http.post(f"{API}/auth/register", json={
            "name": "X", "email": email, "password": "test1234", "role": "hacker"
        })
        assert r.status_code == 400

    def test_me_with_token(self, http, admin_token):
        r = http.get(f"{API}/auth/me", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_token(self, http):
        r = http.get(f"{API}/auth/me")
        assert r.status_code in (401, 403)


# ------------- excel upload -------------
def build_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(["Task Name", "Description", "Assignee", "Role", "HQ", "Frequency",
               "Start Date", "Due Date", "Category", "Target Amount", "Reporting Due Date"])
    ws.append(["TEST Doctor Visit A", "Visit Dr X", "Ravi", "product_executive", "Mumbai",
               "Daily", "2026-07-01", "2026-07-15", "Task", None, "2026-07-16"])
    ws.append(["TEST Sales Collection A", "Collect payment", "Ravi", "product_executive", "Mumbai",
               "Weekly", "2026-07-01", "2026-07-20", "Sales Collection", 50000, "2026-07-21"])
    ws.append(["TEST Q3 Target", "Quarter target", "Ravi", "product_executive", "Delhi",
               "Weekly", "2026-07-01", "2026-07-30", "Target", 200000, "2026-07-31"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestExcelUpload:
    def test_upload_as_admin_inserts_tasks(self, admin_token):
        buf = build_xlsx()
        r = requests.post(
            f"{API}/tasks/upload",
            headers=auth(admin_token),
            files={"file": ("test.xlsx", buf,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["inserted_count"] == 3

    def test_upload_as_non_admin_forbidden(self, user_token):
        buf = build_xlsx()
        r = requests.post(
            f"{API}/tasks/upload",
            headers=auth(user_token),
            files={"file": ("test.xlsx", buf,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 403

    def test_upload_bad_file_type(self, admin_token):
        r = requests.post(
            f"{API}/tasks/upload",
            headers=auth(admin_token),
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400


# ------------- tasks -------------
class TestTasks:
    def test_list_tasks_default(self, http, admin_token):
        r = http.get(f"{API}/tasks", headers=auth(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_tasks_filters(self, http, admin_token):
        for params in [
            {"frequency": "daily"},
            {"category": "sales_collection"},
            {"status": "pending"},
            {"period": "month"},
            {"search": "TEST"},
        ]:
            r = http.get(f"{API}/tasks", headers=auth(admin_token), params=params)
            assert r.status_code == 200, f"params={params} body={r.text}"
            assert isinstance(r.json(), list)

    def test_create_task_manual_and_get(self, http, admin_token):
        payload = {
            "title": "TEST Manual Task",
            "description": "created via API",
            "assignee": "Ravi",
            "role": "product_executive",
            "hq": "Mumbai",
            "frequency": "weekly",
            "category": "task",
            "due_date": "2026-07-25",
        }
        r = http.post(f"{API}/tasks", headers=auth(admin_token), json=payload)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        # verify persistence
        g = http.get(f"{API}/tasks/{tid}", headers=auth(admin_token))
        assert g.status_code == 200
        assert g.json()["title"] == "TEST Manual Task"
        assert g.json()["status"] == "pending"

    def test_patch_status_update(self, http, admin_token):
        r = http.post(f"{API}/tasks", headers=auth(admin_token), json={
            "title": "TEST Patch Task", "due_date": "2026-07-20"})
        tid = r.json()["id"]
        p = http.patch(f"{API}/tasks/{tid}", headers=auth(admin_token),
                       json={"status": "completed"})
        assert p.status_code == 200
        assert p.json()["status"] == "completed"
        assert p.json().get("completed_at")

    def test_patch_collected_amount(self, http, admin_token):
        r = http.post(f"{API}/tasks", headers=auth(admin_token), json={
            "title": "TEST Sales Task", "category": "sales_collection",
            "target_amount": 10000, "due_date": "2026-07-20"})
        tid = r.json()["id"]
        p = http.patch(f"{API}/tasks/{tid}", headers=auth(admin_token),
                       json={"collected_amount": 5500})
        assert p.status_code == 200
        assert p.json()["collected_amount"] == 5500

    def test_delete_task_admin(self, http, admin_token):
        r = http.post(f"{API}/tasks", headers=auth(admin_token),
                      json={"title": "TEST Delete Me", "due_date": "2026-07-20"})
        tid = r.json()["id"]
        d = http.delete(f"{API}/tasks/{tid}", headers=auth(admin_token))
        assert d.status_code == 200
        g = http.get(f"{API}/tasks/{tid}", headers=auth(admin_token))
        assert g.status_code == 404

    def test_delete_task_non_admin_forbidden(self, http, admin_token, user_token):
        r = http.post(f"{API}/tasks", headers=auth(admin_token),
                      json={"title": "TEST No Delete", "due_date": "2026-07-20"})
        tid = r.json()["id"]
        d = http.delete(f"{API}/tasks/{tid}", headers=auth(user_token))
        assert d.status_code == 403


# ------------- dashboard & reports -------------
class TestDashboardReports:
    def test_dashboard(self, http, admin_token):
        r = http.get(f"{API}/dashboard", headers=auth(admin_token))
        assert r.status_code == 200
        data = r.json()
        for k in ("kpis", "sales", "todays_tasks", "recent_tasks", "period"):
            assert k in data
        for k in ("total", "completed", "in_progress", "pending", "overdue", "completion_rate"):
            assert k in data["kpis"]
        for k in ("target_total", "collected_total", "achievement_pct", "count"):
            assert k in data["sales"]

    @pytest.mark.parametrize("period", ["week", "month", "quarter"])
    def test_reports_periods(self, http, admin_token, period):
        r = http.get(f"{API}/reports", headers=auth(admin_token), params={"period": period})
        assert r.status_code == 200
        data = r.json()
        assert data["period"] == period
        for k in ("kpis", "by_hq", "by_assignee", "by_role", "sales", "range"):
            assert k in data
        assert isinstance(data["by_hq"], list)

    def test_meta_filters(self, http, admin_token):
        r = http.get(f"{API}/meta/filters", headers=auth(admin_token))
        assert r.status_code == 200
        for k in ("hqs", "assignees", "roles", "categories", "statuses"):
            assert k in r.json()
