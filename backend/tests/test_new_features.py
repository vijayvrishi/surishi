"""Backend tests for iteration 2 new features:
- POST /api/auth/change-password
- Chairman elevated permissions (upload / delete tasks)
- Chairman user management endpoints + RBAC
- GET /api/reports/pdf
"""
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
CHAIRMAN = "chairman@surishi.in"
HEAD = "head@surishi.com"
PE = "pe@surishi.com"


def _login(email, password=PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    return r


def _token(email, password=PASSWORD):
    r = _login(email, password)
    assert r.status_code == 200, f"login failed for {email}: {r.text}"
    return r.json()["access_token"], r.json()["user"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# =============================================================
# Change password (self-service)
# =============================================================
class TestChangePassword:
    def test_wrong_current_password_returns_400(self):
        tok, _ = _token(PE)
        r = requests.post(
            f"{API}/auth/change-password",
            headers=_auth(tok),
            json={"current_password": "WRONG!!", "new_password": "NewPass@123"},
        )
        assert r.status_code == 400, r.text
        assert "incorrect" in r.text.lower()

    def test_change_password_and_login_then_restore(self):
        tok, _ = _token(PE)
        new_pw = "TempPass@456"
        r = requests.post(
            f"{API}/auth/change-password",
            headers=_auth(tok),
            json={"current_password": PASSWORD, "new_password": new_pw},
        )
        assert r.status_code == 200, r.text

        # old password should now fail
        assert _login(PE, PASSWORD).status_code == 401
        # new password should work
        r2 = _login(PE, new_pw)
        assert r2.status_code == 200, r2.text
        new_tok = r2.json()["access_token"]

        # restore original
        r3 = requests.post(
            f"{API}/auth/change-password",
            headers=_auth(new_tok),
            json={"current_password": new_pw, "new_password": PASSWORD},
        )
        assert r3.status_code == 200, r3.text
        assert _login(PE, PASSWORD).status_code == 200

    def test_short_new_password_rejected(self):
        tok, _ = _token(PE)
        r = requests.post(
            f"{API}/auth/change-password",
            headers=_auth(tok),
            json={"current_password": PASSWORD, "new_password": "abc"},
        )
        # Pydantic Field(min_length=6) -> 422
        assert r.status_code in (400, 422), r.text


# =============================================================
# Chairman admin rights (upload/delete tasks)
# =============================================================
def _make_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append([
        "Task Name", "Description", "Assignee", "Role", "HQ", "Frequency",
        "Start Date", "Due Date", "Category", "Target Amount", "Reporting Due Date",
    ])
    ws.append([
        "TEST Chairman Upload", "via chairman", "Ravi", "product_executive", "Mumbai",
        "Daily", "2026-07-01", "2026-07-15", "Task", None, "2026-07-16",
    ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestChairmanAdminRights:
    def test_chairman_can_upload_excel(self):
        tok, _ = _token(CHAIRMAN)
        buf = _make_xlsx()
        r = requests.post(
            f"{API}/tasks/upload",
            headers=_auth(tok),
            files={"file": ("test.xlsx", buf,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("inserted_count", 0) >= 1

    def test_chairman_can_delete_task(self):
        tok, _ = _token(CHAIRMAN)
        c = requests.post(
            f"{API}/tasks",
            headers=_auth(tok),
            json={"title": "TEST Chairman Delete Me", "due_date": "2026-07-25"},
        )
        assert c.status_code == 200, c.text
        tid = c.json()["id"]
        d = requests.delete(f"{API}/tasks/{tid}", headers=_auth(tok))
        assert d.status_code == 200
        g = requests.get(f"{API}/tasks/{tid}", headers=_auth(tok))
        assert g.status_code == 404


# =============================================================
# Chairman-only user management + RBAC
# =============================================================
class TestUserManagementRBAC:
    @classmethod
    def _create_target_user(cls):
        email = f"test_target_{uuid.uuid4().hex[:8]}@surishi.com"
        r = requests.post(f"{API}/auth/register", json={
            "name": "TEST Target",
            "email": email,
            "password": PASSWORD,
            "role": "product_executive",
            "hq": "Mumbai",
        })
        assert r.status_code == 200, r.text
        return r.json()["user"]

    def test_head_403_on_patch_user(self):
        target = self._create_target_user()
        tok, _ = _token(HEAD)
        r = requests.patch(
            f"{API}/admin/users/{target['id']}",
            headers=_auth(tok),
            json={"role": "marketing_head"},
        )
        assert r.status_code == 403, r.text

    def test_pe_403_on_reset_password(self):
        target = self._create_target_user()
        tok, _ = _token(PE)
        r = requests.post(
            f"{API}/admin/users/{target['id']}/reset-password",
            headers=_auth(tok),
            json={"new_password": "NewPass@123"},
        )
        assert r.status_code == 403, r.text

    def test_head_403_on_delete_user(self):
        target = self._create_target_user()
        tok, _ = _token(HEAD)
        r = requests.delete(
            f"{API}/admin/users/{target['id']}",
            headers=_auth(tok),
        )
        assert r.status_code == 403, r.text

    def test_chairman_can_patch_role_and_hq(self):
        target = self._create_target_user()
        tok, _ = _token(CHAIRMAN)
        r = requests.patch(
            f"{API}/admin/users/{target['id']}",
            headers=_auth(tok),
            json={"role": "business_manager", "hq": "Delhi"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "business_manager"
        assert data["hq"] == "Delhi"

    def test_chairman_invalid_role_400(self):
        target = self._create_target_user()
        tok, _ = _token(CHAIRMAN)
        r = requests.patch(
            f"{API}/admin/users/{target['id']}",
            headers=_auth(tok),
            json={"role": "not_a_role"},
        )
        assert r.status_code == 400, r.text

    def test_chairman_reset_password_and_login(self):
        target = self._create_target_user()
        tok, _ = _token(CHAIRMAN)
        new_pw = "ResetPass@789"
        r = requests.post(
            f"{API}/admin/users/{target['id']}/reset-password",
            headers=_auth(tok),
            json={"new_password": new_pw},
        )
        assert r.status_code == 200, r.text
        # verify new password works
        assert _login(target["email"], new_pw).status_code == 200
        # old (seed) password no longer works
        assert _login(target["email"], PASSWORD).status_code == 401

    def test_chairman_delete_user(self):
        target = self._create_target_user()
        tok, _ = _token(CHAIRMAN)
        r = requests.delete(f"{API}/admin/users/{target['id']}", headers=_auth(tok))
        assert r.status_code == 200
        assert r.json().get("deleted") is True
        # login should now fail (assuming user still had seed password)
        assert _login(target["email"]).status_code == 401

    def test_chairman_cannot_delete_own_account(self):
        tok, me = _token(CHAIRMAN)
        r = requests.delete(f"{API}/admin/users/{me['id']}", headers=_auth(tok))
        assert r.status_code == 400, r.text
        assert "own" in r.text.lower()
        # ensure chairman can still login
        assert _login(CHAIRMAN).status_code == 200


# =============================================================
# PDF reports
# =============================================================
class TestReportsPDF:
    @pytest.mark.parametrize("period", ["week", "month", "quarter"])
    def test_pdf_report(self, period):
        tok, _ = _token(HEAD)
        r = requests.get(f"{API}/reports/pdf", headers=_auth(tok), params={"period": period})
        assert r.status_code == 200, r.text
        assert "application/pdf" in r.headers.get("content-type", "").lower()
        assert r.content[:4] == b"%PDF", f"bad PDF header: {r.content[:8]!r}"
        assert len(r.content) > 500  # non-empty PDF

    def test_pdf_requires_auth(self):
        r = requests.get(f"{API}/reports/pdf", params={"period": "week"})
        assert r.status_code in (401, 403)
