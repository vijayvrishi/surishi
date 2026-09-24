from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
import uuid
import jwt
from io import BytesIO
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta, date
from pwdlib import PasswordHash
from openpyxl import load_workbook

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

pwd_hash = PasswordHash.recommended()
security = HTTPBearer()


def verify_password(password: str, password_hash) -> bool:
    # A missing or malformed stored hash must read as "wrong password",
    # never crash the request with a 500
    if not password_hash or not isinstance(password_hash, str):
        return False
    try:
        return pwd_hash.verify(password, password_hash)
    except Exception:
        return False

app = FastAPI(
    title="Surishi Pharma Marketing Execution API",
    description="Backend API for Surishi Pharmaceuticals marketing task tracking, "
    "sales collection/targets, performance analytics, and reporting.",
    version="1.4.0",
)
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- Constants -------------------
ROLES = [
    "marketing_head", "marketing_deputy_head", "product_executive",
    "general_manager", "ceo", "chairman", "agm", "business_manager", "kam",
]
ADMIN_ROLES = {"marketing_head", "marketing_deputy_head", "chairman"}
# Roles that may create tasks and upload task sheets (admins + CEO)
TASK_CREATOR_ROLES = ADMIN_ROLES | {"ceo"}
# Seniority, highest first. A user sees tasks owned by their own level or
# below; tasks owned by a more senior role are hidden from them.
ROLE_RANK = {
    "chairman": 9, "ceo": 8, "general_manager": 7, "marketing_head": 6, "agm": 6,
    "marketing_deputy_head": 5, "business_manager": 4, "product_executive": 3, "kam": 2,
}
# How roles are written in the task sheet's Assignee / Role columns
ROLE_ALIASES = {
    "chairman": "chairman", "ceo": "ceo",
    "gm": "general_manager", "general manager": "general_manager",
    "agm": "agm", "assistant general manager": "agm",
    "marketing head": "marketing_head", "head marketing": "marketing_head", "head - marketing": "marketing_head",
    "marketing deputy head": "marketing_deputy_head", "deputy head": "marketing_deputy_head",
    "dy head": "marketing_deputy_head", "deputy marketing head": "marketing_deputy_head",
    "bm": "business_manager", "business manager": "business_manager",
    "pe": "product_executive", "product executive": "product_executive",
    "kam": "kam", "key account manager": "kam",
}
USER_MANAGER_ROLES = {"chairman"}
# Features whose visibility the chairman controls per role (Profile is always on;
# Users/permissions are chairman-only regardless).
FEATURES = ["dashboard", "tasks", "performance", "reports"]
FEATURE_LABELS = {"dashboard": "Dashboard", "tasks": "Tasks",
                  "performance": "Performance", "reports": "Reports"}
CATEGORIES = ["task", "sales_collection", "target"]
STATUSES = ["pending", "in_progress", "completed"]
HEADS = ["company", "scientific_inputs", "engagement"]
FREQUENCIES = ["daily", "weekly", "monthly", "quarterly", "yearly", "ongoing", "scheduled", "other"]
FREQUENCY_LABELS = {
    "daily": "Daily", "weekly": "Weekly", "monthly": "Monthly", "quarterly": "Quarterly",
    "yearly": "Yearly", "ongoing": "Ongoing", "scheduled": "As Scheduled", "other": "Other",
}


# ------------------- Models -------------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    role: str
    hq: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    role: str
    hq: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    user: UserPublic


class RegisterResponse(BaseModel):
    detail: str


class ApproveUserRequest(BaseModel):
    role: str
    hq: Optional[str] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    role: Optional[str] = None
    hq: Optional[str] = None
    frequency: str = "monthly"  # free text (Daily / Weekly / Monthly / Ongoing / Per CME schedule ...)
    activity_category: Optional[str] = None  # free-text functional grouping (e.g. "CME planning")
    category: Optional[str] = None  # task | sales_collection | target (auto-derived if omitted)
    head: Optional[str] = None  # company | scientific_inputs | engagement
    units: Optional[List[str]] = None  # per-assignee/HQ participants who must each complete it
    start_date: Optional[str] = None  # YYYY-MM-DD
    due_date: Optional[str] = None
    reporting_due_date: Optional[str] = None
    target_amount: Optional[float] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    collected_amount: Optional[float] = None
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    units: Optional[List[str]] = None


class CompletionUpdate(BaseModel):
    unit: str
    status: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    hq: Optional[str] = None
    name: Optional[str] = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)


class PermissionsUpdate(BaseModel):
    # role -> list of visible feature keys
    permissions: dict


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class PhotoUpload(BaseModel):
    photo_base64: str
    caption: Optional[str] = None


# ------------------- Auth helpers -------------------
def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Only Marketing Head / Deputy Head / Chairman can perform this action")
    return user


async def require_task_creator(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in TASK_CREATOR_ROLES:
        raise HTTPException(status_code=403, detail="You are not allowed to create tasks")
    return user


def task_owner_roles(task: dict) -> set:
    """Role keys a task is assigned to, read from its Role / Assignee text
    (e.g. "GM", "AGM / BM"). Unrecognised text (people, HQs) gives no roles."""
    out = set()
    for field in ("role", "assignee"):
        v = task.get(field)
        if not v:
            continue
        if v in ROLE_RANK:
            out.add(v)
            continue
        for part in re.split(r"[,/&+;\n]+|\band\b", str(v).lower()):
            key = ROLE_ALIASES.get(re.sub(r"[^a-z -]", "", part).strip())
            if key:
                out.add(key)
    return out


def can_see_task(user: dict, task: dict) -> bool:
    """Juniors can't see tasks that belong only to more senior roles."""
    my_rank = ROLE_RANK.get(user.get("role"), 0)
    if user.get("role") == "chairman" or task.get("created_by") == user.get("id"):
        return True
    owners = task_owner_roles(task)
    if not owners:
        return True
    return min(ROLE_RANK[r] for r in owners) <= my_rank


def visible_tasks(user: dict, tasks: List[dict]) -> List[dict]:
    return [t for t in tasks if can_see_task(user, t)]


async def get_visible_task(task_id: str, user: dict, projection=None) -> dict:
    task = await db.tasks.find_one({"id": task_id}, projection or {"_id": 0})
    if not task or not can_see_task(user, task):
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def require_user_manager(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in USER_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only Chairman can manage users")
    return user


# ------------------- Feature access (chairman-controlled) -------------------
async def get_feature_permissions() -> dict:
    """Role -> list of visible features. Missing/unknown roles default to all on."""
    doc = await db.app_meta.find_one({"key": "feature_permissions"})
    stored = (doc or {}).get("value") or {}
    out = {}
    for role in ROLES:
        if role == "chairman":
            out[role] = list(FEATURES)  # chairman always sees everything
        else:
            feats = stored.get(role)
            out[role] = [f for f in feats if f in FEATURES] if isinstance(feats, list) else list(FEATURES)
    return out


async def features_for_user(user: dict) -> list:
    if user.get("role") == "chairman":
        return list(FEATURES)
    perms = await get_feature_permissions()
    return perms.get(user.get("role"), list(FEATURES))


def require_feature(feature: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") == "chairman":
            return user
        if feature not in await features_for_user(user):
            raise HTTPException(status_code=403, detail=f"Your role does not have access to {FEATURE_LABELS.get(feature, feature)}")
        return user
    return dep


# ------------------- Date helpers -------------------
def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def period_range(period: str):
    t = utc_today()
    if period == "week":
        start = t - timedelta(days=t.weekday())
        end = start + timedelta(days=6)
    elif period == "quarter":
        q = (t.month - 1) // 3
        start = date(t.year, q * 3 + 1, 1)
        end_month = q * 3 + 3
        if end_month == 12:
            end = date(t.year, 12, 31)
        else:
            end = date(t.year, end_month + 1, 1) - timedelta(days=1)
    else:  # month
        start = date(t.year, t.month, 1)
        if t.month == 12:
            end = date(t.year, 12, 31)
        else:
            end = date(t.year, t.month + 1, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def parse_excel_date(value) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y", "%d %b %Y", "%d-%b-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ------------------- Excel header mapping -------------------
HEADER_MAP = {
    "task name": "title", "task": "title", "title": "title", "task title": "title", "activity": "title",
    "description": "description", "details": "description", "task description": "description",
    "assignee": "assignee", "assigned to": "assignee", "assignee name": "assignee", "responsible person": "assignee",
    "assignees": "units", "units": "units", "hq list": "units", "hqs": "units", "team": "units",
    "participants": "units", "assigned hqs": "units", "responsible hqs": "units",
    "role": "role", "roles and responsibilities": "role", "responsibility": "role", "designation": "role",
    "hq": "hq", "headquarter": "hq", "headquarters": "hq", "hq name": "hq",
    "frequency": "frequency", "freq": "frequency", "task frequency": "frequency", "recurrence": "frequency",
    "start date": "start_date", "from date": "start_date",
    "due date": "due_date", "end date": "due_date", "deadline": "due_date", "timeline": "due_date", "to date": "due_date",
    "start / due date": "due_date", "start/due date": "due_date", "start due date": "due_date", "due": "due_date",
    "category": "activity_category", "type": "activity_category", "task type": "activity_category",
    "activity area": "activity_category", "activity category": "activity_category", "area": "activity_category",
    "head": "head", "activity head": "head", "activity type": "head", "segment": "head", "activity segment": "head",
    "target amount": "target_amount", "target": "target_amount", "sales target": "target_amount",
    "collected amount": "collected_amount", "collection": "collected_amount", "sales collection": "collected_amount", "collection amount": "collected_amount",
    "reporting due date": "reporting_due_date", "reporting date": "reporting_due_date",
    "report due date": "reporting_due_date", "due date of reporting": "reporting_due_date",
}


def norm_header(h) -> str:
    return str(h).strip().lower().replace("_", " ").replace("*", "").strip()


def norm_category(v) -> str:
    if not v:
        return "task"
    s = str(v).strip().lower()
    if "collection" in s:
        return "sales_collection"
    if "target" in s:
        return "target"
    return "task"


def norm_frequency(v) -> str:
    """Bucket a free-text frequency into a known value; unknown text -> 'scheduled' or 'other'."""
    if not v:
        return "monthly"
    s = str(v).strip().lower()
    if "dai" in s or s == "d":
        return "daily"
    if "week" in s:
        return "weekly"
    if "month" in s:
        return "monthly"
    if "quarter" in s:
        return "quarterly"
    if "year" in s or "annual" in s:
        return "yearly"
    if "ongoing" in s or "continu" in s:
        return "ongoing"
    if "schedul" in s or "per " in s or "as " in s or "cme" in s:
        return "scheduled"
    return "other"


def clean_str(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def norm_head(v) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip().lower()
    if "scien" in s or "input" in s:
        return "scientific_inputs"
    if "engag" in s:
        return "engagement"
    if "comp" in s:
        return "company"
    return None


def to_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").replace("₹", "").strip())
    except ValueError:
        return None


def period_start_for_frequency(freq: str) -> Optional[str]:
    """First day of the current period for a recurring frequency, used as the due
    date when a task has no explicit one. Non-periodic frequencies return None."""
    t = utc_today()
    if freq == "daily":
        return t.isoformat()
    if freq == "weekly":
        return (t - timedelta(days=t.weekday())).isoformat()
    if freq == "monthly":
        return date(t.year, t.month, 1).isoformat()
    if freq == "quarterly":
        q = (t.month - 1) // 3
        return date(t.year, q * 3 + 1, 1).isoformat()
    if freq == "yearly":
        return date(t.year, 1, 1).isoformat()
    return None  # ongoing / scheduled / other -> no anchored date


def parse_units(v) -> List[str]:
    """Split a free-text list of participants (comma / semicolon / slash / newline separated)."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        items = [str(x) for x in v]
    else:
        items = re.split(r"[,;\n/]+", str(v))
    seen, out = set(), []
    for it in items:
        s = it.strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def build_completions(units: List[str], existing: Optional[list] = None) -> list:
    prev = {c["unit"]: c for c in (existing or [])}
    out = []
    for u in units:
        e = prev.get(u)
        out.append({
            "unit": u,
            "status": (e or {}).get("status", "pending"),
            "updated_at": (e or {}).get("updated_at"),
            "updated_by": (e or {}).get("updated_by"),
        })
    return out


def derive_completion(completions: list):
    """Return (overall_status, pct, completed_count, total) from per-unit completions."""
    total = len(completions)
    if total == 0:
        return None, None, 0, 0
    completed = sum(1 for c in completions if c.get("status") == "completed")
    if completed == total:
        status = "completed"
    elif any(c.get("status") in ("in_progress", "completed") for c in completions):
        status = "in_progress"
    else:
        status = "pending"
    return status, round(completed / total * 100, 1), completed, total


def task_doc(data: dict, created_by: str, source: str = "manual") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    freq = data.get("frequency") or "monthly"
    # Anchor undated recurring tasks to the first day of the concerned period
    due = data.get("due_date") or period_start_for_frequency(freq)
    activity_category = data.get("activity_category")
    # Derive the internal enum from the free-text grouping unless explicitly set
    category = data.get("category") or norm_category(activity_category)
    freq_label = data.get("frequency_label") or data.get("frequency")
    units = data.get("units") or []
    completions = build_completions(units)
    derived_status, pct, completed_n, total_n = derive_completion(completions)
    status = derived_status if units else "pending"
    return {
        "id": str(uuid.uuid4()),
        "title": data.get("title") or "",
        "description": data.get("description"),
        "assignee": data.get("assignee"),
        "role": data.get("role"),
        "hq": data.get("hq"),
        "frequency": freq,
        "frequency_label": freq_label,
        "category": category or "task",
        "activity_category": activity_category,
        "head": data.get("head"),
        "units": units,
        "completions": completions,
        "completion_completed": completed_n,
        "completion_total": total_n,
        "completion_pct": pct,
        "start_date": data.get("start_date"),
        "due_date": due,
        "reporting_due_date": data.get("reporting_due_date"),
        "target_amount": data.get("target_amount"),
        "collected_amount": data.get("collected_amount"),
        "status": status,
        "month": due[:7] if due else None,
        "source": source,  # "manual" (created in-app) | "sheet" (Excel upload or the seeded task sheet)
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def find_header_row(rows) -> int:
    """Locate the header row: the first row (within the first 15) that maps to a title column."""
    for i, row in enumerate(rows[:15]):
        if not row:
            continue
        for h in row:
            if h is not None and HEADER_MAP.get(norm_header(h)) == "title":
                return i
    return 0


# ------------------- Monthly activity plan workbook -------------------
# The marketing team's monthly plan (e.g. "oct_plan.xlsx") is not a task table:
# it has a DAILY COMMUNICATION sheet (Date / Brand / WhatsApp Communication),
# an ACTIVITY PLANNER sheet (WEEK 1..4 blocks of label/value rows) and a
# REQUIREMENT sheet (inputs per MR). Each is turned into tasks here.
PLAN_FIELDS = ["Brands Covered", "Theme", "Objective", "Inputs Used", "Input Content",
               "Input Allocation Strategy", "Step-wise Modus Operandi", "Detailing Communication",
               "POB Strategy", "Monitoring", "Remarks"]


def _cell_text(v) -> Optional[str]:
    if v is None:
        return None
    s = re.sub(r"[ \t\xa0]+", " ", str(v)).strip()
    return s or None


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def _plan_sheet(wb, *words):
    for sn in wb.sheetnames:
        low = sn.lower()
        if all(w in low for w in words):
            return wb[sn]
    return None


def _plan_month_start(wb) -> date:
    daily = _plan_sheet(wb, "daily")
    if daily is not None:
        for row in daily.iter_rows(values_only=True):
            iso = parse_excel_date(row[0]) if row and isinstance(row[0], (datetime, date)) else None
            if iso:
                d = date.fromisoformat(iso)
                return date(d.year, d.month, 1)
    for sn in wb.sheetnames:
        m = parse_sheet_month(sn)
        if m:
            return date(int(m[:4]), int(m[5:]), 1)
    t = utc_today()
    return date(t.year, t.month, 1)


def is_plan_workbook(wb) -> bool:
    return any(("activity planner" in sn.lower() or "daily communication" in sn.lower())
               for sn in wb.sheetnames)


def parse_plan_workbook(wb) -> List[dict]:
    """Tasks (as task_doc input dicts) from a monthly activity plan workbook."""
    month_start = _plan_month_start(wb)
    month_end = _month_end(month_start)
    month_label = month_start.strftime("%b %Y")
    tasks = []

    # 1. Daily WhatsApp communication to doctors — one task per day
    daily = _plan_sheet(wb, "daily")
    if daily is not None:
        for row in daily.iter_rows(values_only=True):
            if not row or not isinstance(row[0], (datetime, date)):
                continue
            day = parse_excel_date(row[0])
            brand = _cell_text(row[1] if len(row) > 1 else None)
            msg = _cell_text(row[2] if len(row) > 2 else None)
            if not msg:
                continue
            tasks.append({
                "title": f"WhatsApp communication – {brand}" if brand else "WhatsApp communication",
                "description": msg,
                "frequency": "daily", "frequency_label": "Daily",
                "activity_category": "Daily Doctor Communication",
                "head": "engagement",
                "start_date": day, "due_date": day,
            })

    # 2. Weekly activity drives
    planner = _plan_sheet(wb, "activity", "plan")
    if planner is not None:
        blocks = []  # (block label, {field: [col1, col2, ...]})
        for row in planner.iter_rows(values_only=True):
            if not row:
                continue
            label = _cell_text(row[0])
            values = [_cell_text(v) for v in row[1:]]
            if not label:
                continue
            if not any(values):
                blocks.append((label, {}))
                continue
            if blocks:
                blocks[-1][1][label.lower()] = values
        week_nums = [int(m.group(1)) for m in
                     (re.search(r"week\s*(\d+)", b[0], re.IGNORECASE) for b in blocks) if m]
        last_week = max(week_nums, default=4)
        for block_label, fields in blocks:
            names = fields.get("activity name") or []
            wk = re.search(r"week\s*(\d+)", block_label, re.IGNORECASE)
            if wk:
                n = int(wk.group(1))
                start = min(month_start + timedelta(days=7 * (n - 1)), month_end)
                # The plan's last week runs to month end (e.g. Week 4 = 22nd–31st)
                end = month_end if n >= last_week else min(start + timedelta(days=6), month_end)
                freq_label = f"Week {n}"
            else:
                start, end, freq_label = month_start, month_end, block_label
            cols = [i for i, v in enumerate(names) if v]
            for i in cols:
                def fv(key):
                    vals = fields.get(key.lower()) or []
                    return vals[i] if i < len(vals) and vals[i] else (vals[0] if vals else None)
                title = names[i]
                theme = fv("Theme")
                if len(cols) > 1 and theme:
                    title = f"{title} – {theme}"
                desc = "\n\n".join(f"{k}: {fv(k)}" for k in PLAN_FIELDS if fv(k))
                tasks.append({
                    "title": title,
                    "description": desc or None,
                    "frequency": "weekly" if wk else "monthly",
                    "frequency_label": freq_label,
                    "activity_category": f"Activity Plan {month_label}",
                    "head": "engagement",
                    "start_date": start.isoformat(), "due_date": end.isoformat(),
                })

    # 3. Inputs to arrange, per activity (allocation per MR)
    req = _plan_sheet(wb, "requirement")
    if req is not None:
        section, items = None, []

        def close():
            if section and items:
                tasks.append({
                    "title": f"Arrange inputs – {section}",
                    "description": "Allocation per MR:\n" + "\n".join(f"• {n}: {q}" for n, q in items),
                    "frequency": "monthly", "frequency_label": "Monthly",
                    "activity_category": f"Input Requirement {month_label}",
                    "head": "scientific_inputs",
                    "start_date": month_start.isoformat(), "due_date": month_start.isoformat(),
                })

        for row in req.iter_rows(values_only=True):
            if not row:
                continue
            label = _cell_text(row[0])
            qty = row[1] if len(row) > 1 else None
            if not label or label.lower().startswith("activity / input"):
                continue
            if qty is None:
                close()
                section, items = label, []
            else:
                items.append((label, int(qty) if isinstance(qty, float) and qty.is_integer() else qty))
        close()
    return tasks


# ------------------- Auth routes -------------------
@api_router.post("/auth/register", response_model=RegisterResponse)
async def register(req: RegisterRequest):
    if req.role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    existing = await db.users.find_one({"email": req.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user = {
        "id": str(uuid.uuid4()),
        "name": req.name.strip(),
        "email": req.email.lower(),
        "role": req.role,  # requested designation — chairman confirms/changes it on approval
        "hq": req.hq,
        "status": "pending",
        "password_hash": pwd_hash.hash(req.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(dict(user))
    return RegisterResponse(
        detail="Registration submitted. An administrator will review and approve your "
        "account before you can sign in."
    )


@api_router.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if not user or not verify_password(req.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("status") == "pending":
        raise HTTPException(
            status_code=403,
            detail="Your account is pending Admin approval. You'll be able to sign in once an administrator approves it.",
        )
    public = UserPublic(**{k: user.get(k) for k in ("id", "name", "email", "role", "hq")})
    return TokenResponse(access_token=create_token(user), user=public)


@api_router.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**{k: user.get(k) for k in ("id", "name", "email", "role", "hq")})


@api_router.get("/me/features")
async def my_features(user: dict = Depends(get_current_user)):
    """The features the current user is allowed to see (drives the nav)."""
    return {
        "features": await features_for_user(user),
        "all_features": FEATURES,
        "labels": FEATURE_LABELS,
        "is_user_manager": user.get("role") in USER_MANAGER_ROLES,
    }


@api_router.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    doc = await db.users.find_one({"id": user["id"]})
    if not doc or not verify_password(req.current_password, doc.get("password_hash")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": pwd_hash.hash(req.new_password)}},
    )
    return {"detail": "Password updated successfully"}


@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    user = await db.users.find_one({"email": req.email.lower()}, {"_id": 0, "id": 1, "name": 1, "email": 1})
    if user:
        pending = await db.password_reset_requests.find_one({"email": user["email"], "status": "pending"})
        if not pending:
            await db.password_reset_requests.insert_one({
                "id": str(uuid.uuid4()),
                "email": user["email"],
                "user_name": user.get("name"),
                "status": "pending",
                "requested_at": datetime.now(timezone.utc).isoformat(),
            })
    # Same response whether or not the account exists, to avoid leaking emails
    return {"detail": "Request received. Your administrator will reset your password and share it with you."}


@api_router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    users = await db.users.find({"status": {"$ne": "pending"}}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


# ------------------- Registration approval (Chairman only) -------------------
@api_router.get("/admin/pending-users")
async def list_pending_users(admin: dict = Depends(require_user_manager)):
    return await db.users.find(
        {"status": "pending"}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", 1).to_list(500)


@api_router.post("/admin/pending-users/{user_id}/approve")
async def approve_user(user_id: str, req: ApproveUserRequest, admin: dict = Depends(require_user_manager)):
    if req.role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    updates = {"status": "approved", "role": req.role}
    if req.hq is not None:
        updates["hq"] = req.hq
    await db.users.update_one({"id": user_id}, {"$set": updates})
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})


@api_router.delete("/admin/pending-users/{user_id}")
async def reject_user(user_id: str, admin: dict = Depends(require_user_manager)):
    result = await db.users.delete_one({"id": user_id, "status": "pending"})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pending registration not found")
    return {"deleted": True}


# ------------------- User management (Chairman only) -------------------
@api_router.patch("/admin/users/{user_id}")
async def admin_update_user(user_id: str, req: AdminUserUpdate, admin: dict = Depends(require_user_manager)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "role" in updates and updates["role"] not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated


@api_router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, req: AdminResetPasswordRequest, admin: dict = Depends(require_user_manager)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": pwd_hash.hash(req.new_password)}},
    )
    await db.password_reset_requests.update_many(
        {"email": target["email"], "status": "pending"},
        {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"detail": "Password reset successfully"}


@api_router.get("/admin/permissions")
async def get_permissions(admin: dict = Depends(require_user_manager)):
    """Full role → features matrix for the chairman to edit."""
    return {
        "features": FEATURES,
        "labels": FEATURE_LABELS,
        "roles": [r for r in ROLES if r != "chairman"],
        "role_labels": {r: r.replace("_", " ").title() for r in ROLES},
        "permissions": {r: v for r, v in (await get_feature_permissions()).items() if r != "chairman"},
    }


@api_router.put("/admin/permissions")
async def set_permissions(req: PermissionsUpdate, admin: dict = Depends(require_user_manager)):
    cleaned = {}
    for role, feats in (req.permissions or {}).items():
        if role in ROLES and role != "chairman":
            cleaned[role] = [f for f in (feats or []) if f in FEATURES]
    await db.app_meta.update_one(
        {"key": "feature_permissions"},
        {"$set": {"key": "feature_permissions", "value": cleaned,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": admin.get("name")}},
        upsert=True,
    )
    return {"permissions": {r: v for r, v in (await get_feature_permissions()).items() if r != "chairman"}}


@api_router.get("/admin/reset-requests")
async def list_reset_requests(admin: dict = Depends(require_user_manager)):
    return await db.password_reset_requests.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("requested_at", -1).to_list(200)


@api_router.delete("/admin/reset-requests/{request_id}")
async def dismiss_reset_request(request_id: str, admin: dict = Depends(require_user_manager)):
    result = await db.password_reset_requests.delete_one({"id": request_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"deleted": True}


@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(require_user_manager)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}


@api_router.delete("/admin/data")
async def admin_clear_data(admin: dict = Depends(require_user_manager)):
    """Delete every task and all uploaded performance sheets. Users are kept.
    Also clears the task-sheet seed marker so nothing repopulates."""
    tasks_deleted = (await db.tasks.delete_many({})).deleted_count
    perf_deleted = {}
    for key, coll in PERF_COLLECTIONS.items():
        perf_deleted[key] = (await db[coll].delete_many({})).deleted_count
    await db.app_meta.delete_one({"key": "seed_task_sheet"})
    return {"tasks_deleted": tasks_deleted, "performance_deleted": perf_deleted}


# ------------------- Task routes -------------------
@api_router.post("/tasks")
async def create_task(req: TaskCreate, user: dict = Depends(require_task_creator)):
    data = req.model_dump()
    data["units"] = parse_units(data.get("units"))
    data["activity_category"] = clean_str(data.get("activity_category"))
    # Keep an explicit enum choice if given, else derive from the activity grouping
    if data.get("category") in CATEGORIES:
        data["category"] = data["category"]
    else:
        data["category"] = norm_category(data.get("activity_category"))
    data["frequency_label"] = clean_str(data.get("frequency"))
    data["frequency"] = norm_frequency(data.get("frequency"))
    data["head"] = norm_head(data.get("head"))
    doc = task_doc(data, user["id"])
    if not doc["title"].strip():
        raise HTTPException(status_code=400, detail="Title is required")
    await db.tasks.insert_one(dict(doc))
    return doc


@api_router.get("/tasks")
async def list_tasks(
    frequency: Optional[str] = None,
    hq: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    activity_category: Optional[str] = None,
    head: Optional[str] = None,
    assignee: Optional[str] = None,
    role: Optional[str] = None,
    period: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(require_feature("tasks")),
):
    query = {}
    if frequency:
        query["frequency"] = frequency
    if hq:
        query["hq"] = hq
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if activity_category:
        query["activity_category"] = activity_category
    if head:
        query["head"] = head
    if assignee:
        query["assignee"] = assignee
    if role:
        query["role"] = role
    if period in ("week", "month", "quarter"):
        start, end = period_range(period)
        query["due_date"] = {"$gte": start, "$lte": end}
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    pipeline = [
        {"$match": query},
        {"$sort": {"due_date": 1}},
        {"$limit": 5000},
        {"$addFields": {"photo_count": {"$size": {"$ifNull": ["$photos", []]}}}},
        {"$project": {"_id": 0, "photos": 0}},
    ]
    tasks = await db.tasks.aggregate(pipeline).to_list(5000)
    return visible_tasks(user, tasks)[:1000]


@api_router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(require_feature("tasks"))):
    return await get_visible_task(task_id, user)


@api_router.patch("/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdate, user: dict = Depends(require_feature("tasks"))):
    task = await get_visible_task(task_id, user)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}

    # Editing the participant list rebuilds completions and re-derives status
    if "units" in updates:
        units = parse_units(updates.pop("units"))
        completions = build_completions(units, task.get("completions"))
        derived, pct, comp_n, total_n = derive_completion(completions)
        updates.update({
            "units": units, "completions": completions,
            "completion_completed": comp_n, "completion_total": total_n,
            "completion_pct": pct,
        })
        if units:
            updates["status"] = derived  # derived overall for multi-unit tasks

    has_units = bool(updates.get("units", task.get("units")))
    if "status" in updates:
        if updates["status"] not in STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        # For multi-unit tasks the overall status is derived, not set directly
        if has_units and "units" not in updates:
            raise HTTPException(status_code=400, detail="This task tracks completion per assignee; update each assignee's status instead")
        if updates["status"] == "completed":
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
    if "due_date" in updates:
        updates["month"] = updates["due_date"][:7]
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.tasks.update_one({"id": task_id}, {"$set": updates})
    updated = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return updated


@api_router.patch("/tasks/{task_id}/completion")
async def update_completion(task_id: str, req: CompletionUpdate, user: dict = Depends(get_current_user)):
    task = await get_visible_task(task_id, user)
    if req.status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    completions = task.get("completions") or []
    units = task.get("units") or []
    if req.unit not in units:
        raise HTTPException(status_code=404, detail="This assignee is not part of the task")
    now = datetime.now(timezone.utc).isoformat()
    found = False
    for c in completions:
        if c["unit"] == req.unit:
            c["status"] = req.status
            c["updated_at"] = now
            c["updated_by"] = user.get("name")
            found = True
            break
    if not found:
        completions.append({"unit": req.unit, "status": req.status, "updated_at": now, "updated_by": user.get("name")})
    derived, pct, comp_n, total_n = derive_completion(completions)
    set_fields = {
        "completions": completions, "status": derived,
        "completion_completed": comp_n, "completion_total": total_n,
        "completion_pct": pct, "updated_at": now,
    }
    if derived == "completed":
        set_fields["completed_at"] = now
    await db.tasks.update_one({"id": task_id}, {"$set": set_fields})
    return await db.tasks.find_one({"id": task_id}, {"_id": 0})


@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(require_admin)):
    result = await db.tasks.delete_one({"id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}


# ------------------- Task photos (marketing activity proof) -------------------
@api_router.post("/tasks/{task_id}/photos")
async def add_task_photo(task_id: str, req: PhotoUpload, user: dict = Depends(get_current_user)):
    task = await get_visible_task(task_id, user)
    if len(req.photo_base64) > 4_000_000:
        raise HTTPException(status_code=400, detail="Photo is too large. Please retake with lower quality.")
    if len(task.get("photos") or []) >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 photos per task")
    photo = {
        "id": str(uuid.uuid4()),
        "data": req.photo_base64,
        "caption": req.caption,
        "uploaded_by": user["name"],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tasks.update_one({"id": task_id}, {"$push": {"photos": photo}})
    return photo


@api_router.delete("/tasks/{task_id}/photos/{photo_id}")
async def delete_task_photo(task_id: str, photo_id: str, user: dict = Depends(get_current_user)):
    await get_visible_task(task_id, user, {"_id": 0, "photos": 0})
    result = await db.tasks.update_one({"id": task_id}, {"$pull": {"photos": {"id": photo_id}}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}


# ------------------- Excel upload -------------------
@api_router.post("/tasks/upload")
async def upload_excel(file: UploadFile = File(...), replace: bool = False, user: dict = Depends(require_task_creator)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx Excel files are supported")
    contents = await file.read()
    try:
        wb = load_workbook(filename=BytesIO(contents), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the Excel file. Please check the format.")
    if is_plan_workbook(wb):
        return await save_plan_tasks(wb, user, file.filename)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel file has no data rows")

    header_idx = find_header_row(rows)
    headers = rows[header_idx]
    col_map = {}
    for idx, h in enumerate(headers):
        if h is None:
            continue
        key = HEADER_MAP.get(norm_header(h))
        if key and key not in col_map:
            col_map[key] = idx
    if "title" not in col_map:
        raise HTTPException(status_code=400, detail="Could not find a 'Task Name' column in the Excel file")

    inserted = []
    skipped = []
    for row_num, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        def cell(key):
            i = col_map.get(key)
            return row[i] if i is not None and i < len(row) else None

        title = cell("title")
        if title is None or str(title).strip() == "":
            if any(v is not None and str(v).strip() != "" for v in row):
                skipped.append({"row": row_num, "reason": "Missing task name"})
            continue
        freq_raw = clean_str(cell("frequency"))
        data = {
            "title": str(title).strip(),
            "description": clean_str(cell("description")),
            "assignee": clean_str(cell("assignee")),
            "role": clean_str(cell("role")),
            "hq": clean_str(cell("hq")),
            "frequency": norm_frequency(freq_raw),
            "frequency_label": freq_raw,
            "activity_category": clean_str(cell("activity_category")),
            "units": parse_units(cell("units")),
            "head": norm_head(cell("head")),
            "start_date": parse_excel_date(cell("start_date")),
            "due_date": parse_excel_date(cell("due_date")),
            "reporting_due_date": parse_excel_date(cell("reporting_due_date")),
            "target_amount": to_float(cell("target_amount")),
            "collected_amount": to_float(cell("collected_amount")),
        }
        inserted.append(task_doc(data, user["id"], source="sheet"))
    return await save_uploaded_tasks(inserted, skipped, replace, file.filename)


PLAN_CARRY_FIELDS = ("status", "completions", "completion_completed", "completion_total",
                     "completion_pct", "completed_at", "collected_amount", "photos")


async def save_plan_tasks(wb, user: dict, filename: str) -> dict:
    """Monthly plan upload. Re-uploading a month's plan replaces that month's
    plan tasks only (other months and manual tasks are untouched); progress
    already recorded on a task (status, per-assignee completion, photos) is
    kept when the same task (title + due date) is in the new file."""
    plan = parse_plan_workbook(wb)
    if not plan:
        raise HTTPException(status_code=400, detail="No activities could be read from this plan file")
    plan_month = _plan_month_start(wb).isoformat()[:7]
    existing = await db.tasks.find({"plan_month": plan_month}, {"_id": 0}).to_list(5000)
    prior = {(t.get("title"), t.get("due_date")): t for t in existing}
    docs = []
    for d in plan:
        doc = task_doc(d, user["id"], source="sheet")
        doc["plan_month"] = plan_month
        old = prior.get((doc["title"], doc["due_date"]))
        if old:
            for k in PLAN_CARRY_FIELDS:
                if old.get(k) is not None:
                    doc[k] = old[k]
        docs.append(doc)
    if existing:
        await db.tasks.delete_many({"plan_month": plan_month})
    await db.tasks.insert_many([dict(d) for d in docs])
    return {"inserted_count": len(docs), "skipped": [], "filename": filename,
            "replaced_count": len(existing) if existing else None, "plan_month": plan_month}


async def save_uploaded_tasks(inserted: List[dict], skipped: list, replace: bool, filename: str) -> dict:
    replaced_count = None
    if replace:
        if not inserted:
            raise HTTPException(
                status_code=400,
                detail="No valid task rows found in this file — nothing was replaced, to avoid losing existing data.",
            )
        # Replace only sheet-sourced tasks (prior uploads / the seeded task sheet);
        # manually created tasks and their status/photos are left untouched.
        replaced_count = (await db.tasks.delete_many({"source": "sheet"})).deleted_count

    if inserted:
        await db.tasks.insert_many([dict(d) for d in inserted])
    return {
        "inserted_count": len(inserted), "skipped": skipped, "filename": filename,
        "replaced_count": replaced_count,
    }


# ------------------- Performance sheets (Brand / Territory / Management) -------------------
MONTH_MAP = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
             "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


MONTH_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", re.IGNORECASE)


def find_month_num(text: str) -> Optional[int]:
    # Whole-word match so e.g. "Primary" is not read as "mar"
    m = MONTH_RE.search(text or "")
    return MONTH_MAP[m.group(1).lower()] if m else None


def parse_sheet_month(sheet_name: str) -> Optional[str]:
    n = sheet_name.lower()
    month = find_month_num(n)
    if month is None:
        return None
    year = utc_today().year
    m4 = re.search(r"20\d{2}", n)
    if m4:
        year = int(m4.group(0))
    else:
        m2 = re.search(r"\b(\d{2})\b", n)
        if m2:
            year = 2000 + int(m2.group(1))
    return f"{year}-{month:02d}"


def sheet_title_month(ws) -> Optional[int]:
    """Month named in a sheet's title row (e.g. "Brand Performance-Sep",
    "September Sec Status"). The title is what the data actually covers, so it
    wins over a stale tab name copied from last month's sheet."""
    for row in ws.iter_rows(max_row=3, values_only=True):
        cells = [str(c).strip() for c in row if isinstance(c, str) and c.strip()]
        if not cells:
            continue
        if cells[0].lower() == "brand":  # header row, not a title
            return None
        return find_month_num(" ".join(cells))
    return None


def resolve_sheet_month(ws, sheet_name: str, filename: str) -> Optional[str]:
    base = parse_sheet_month(sheet_name) or parse_sheet_month(filename or "")
    title_month = sheet_title_month(ws)
    if title_month is None:
        return base
    year = int(base[:4]) if base else utc_today().year
    return f"{year}-{title_month:02d}"


def month_to_date(weeks: list) -> Optional[float]:
    """Weekly columns in every performance sheet are cumulative month-to-date
    ("Sec till 7th", "till 14th", ...), so the month's sales so far is the
    latest week that has a value — not the sum of the weeks."""
    return next((w for w in reversed(weeks) if w is not None), None)


def apply_current_week(docs: List[dict]) -> None:
    """Set each row's month-to-date sales from the sheet's current week: the
    last week column any row has filled. A row left blank in that week counts
    as 0 there (as the sheet's own Achievement % does), provided it has figures
    in an earlier week."""
    keys = ("w1", "w2", "w3", "w4")
    filled = [i for i, k in enumerate(keys) if any(d.get(k) is not None for d in docs)]
    if not filled:
        return
    cur = keys[filled[-1]]
    for d in docs:
        if all(d.get(k) is None for k in keys):
            sales = None
        else:
            sales = d.get(cur) if d.get(cur) is not None else 0.0
        d["sales_total"] = sales
        t = d.get("target")
        d["achievement_pct"] = round(sales / t * 100, 1) if (t and sales is not None) else None


def sheet_text(ws, max_row=8) -> str:
    parts = []
    for row in ws.iter_rows(max_row=max_row, values_only=True):
        for c in row:
            if c is not None:
                parts.append(str(c))
    return " ".join(parts).lower()


def detect_perf_type(wb) -> Optional[str]:
    for sn in wb.sheetnames:
        text = sheet_text(wb[sn])
        if "total primary sales" in text or "active doctors" in text:
            return "management"
        if "h.q" in text or "be/kam" in text or "territory management" in text or "sec status" in text:
            return "territory"
        if "brand" in text and "target" in text:
            return "brand"
    return None


def parse_brand_sheet(ws, month: str) -> List[dict]:
    rows = list(ws.iter_rows(values_only=True))
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0] is not None and str(row[0]).strip().lower() == "brand":
            header_idx = i
            break
    if header_idx is None:
        return []
    docs = []
    for row in rows[header_idx + 1:]:
        if not row or row[0] is None:
            continue
        brand = str(row[0]).strip()
        if not brand or brand.lower() == "total":
            continue

        def g(i):
            return row[i] if i < len(row) else None

        target = to_float(g(1))
        weeks = [to_float(g(i)) for i in (2, 3, 4, 5)]
        total = month_to_date(weeks)
        ach = round(total / target * 100, 1) if (target and total is not None) else None
        docs.append({
            "id": str(uuid.uuid4()),
            "month": month,
            "brand": brand,
            "target": target,
            "w1": weeks[0], "w2": weeks[1], "w3": weeks[2], "w4": weeks[3],
            "sales_total": total,
            "achievement_pct": ach,
            "growth": str(g(6)).strip() if g(6) is not None else None,
            "top_territory": str(g(7)).strip() if g(7) is not None else None,
            "low_territory": str(g(8)).strip() if g(8) is not None else None,
        })
    apply_current_week(docs)
    return docs


MGMT_METRICS = [
    ("total primary sales", "primary_sales", "numeric"),
    ("total secondary sales", "secondary_sales", "numeric"),
    ("monthly run rate", "run_rate", "numeric"),
    ("active doctors", "active_doctors", "numeric"),
    ("new prescribers", "new_prescribers", "numeric"),
    ("top brand", "top_brand", "text"),
    ("lowest brand", "lowest_brand", "text"),
    ("strong territory", "strong_territory", "text"),
    ("weak territory", "weak_territory", "text"),
]


def parse_mgmt_sheet(ws, month: str) -> Optional[dict]:
    metrics = {}
    for row in ws.iter_rows(values_only=True):
        if not row or row[0] is None:
            continue
        label = str(row[0]).strip().lower()
        for match, key, kind in MGMT_METRICS:
            if match in label:
                def g(i):
                    return row[i] if i < len(row) else None
                if kind == "numeric":
                    weeks = [to_float(g(i)) for i in (1, 2, 3, 4)]
                    total = to_float(g(5))
                    metrics[key] = {
                        "weeks": weeks,
                        # Weeks are month-to-date; when the TOTAL cell is blank
                        # (month still running) the latest week is the total so far.
                        "total": total if total is not None else month_to_date(weeks),
                    }
                else:
                    metrics[key] = {
                        "weeks": [str(g(i)).strip() if g(i) is not None else None for i in (1, 2, 3, 4)],
                    }
                break
    if not metrics:
        return None
    return {"id": str(uuid.uuid4()), "month": month, "metrics": metrics}


TERR_HEADER_SKIP = ("h.q", "region / hq", "territory management")
TERR_GROUP_WORDS = ("region", "zone", "team", "india")


def parse_territory_sheet(ws, month: str) -> List[dict]:
    """Territory rows are grouped under region/zone labels. A label with no
    figures is a heading for the rows below it; a label carrying figures is a
    subtotal of the rows above it ("Total", "Indore Region", "South Zone",
    "All India"). Subtotal rows are never stored as territories."""
    docs = []
    pending = []           # data rows not yet assigned a region
    heading = None         # region from the latest heading row still open
    last_label = None      # most recent region/zone name seen, as a fallback
    after_total = False    # the previous group was closed by a plain "Total" row
    prev_hq = None

    def flush(region):
        for d in pending:
            d["region"] = region or "Other"
        pending.clear()

    for row in ws.iter_rows(values_only=True):
        if not row:
            continue

        def g(i):
            return row[i] if i < len(row) else None

        s0 = str(g(0)).strip() if g(0) is not None else ""
        name = str(g(1)).strip() if g(1) is not None else ""
        low = s0.lower()
        if not s0 and not name:
            continue
        if any(low.startswith(p) for p in TERR_HEADER_SKIP) or "sec status" in low:
            continue

        target = to_float(g(3))
        weeks = [to_float(g(i)) for i in (4, 5, 6, 7)]
        has_figures = target is not None or any(w is not None for w in weeks)

        if s0 and not name and (low.startswith("total") or low.startswith("zone total")
                                or any(w in low for w in TERR_GROUP_WORDS)):
            label = re.sub(r"\s+", " ", re.sub(r"\s*\(.*\)\s*$", "", s0)).strip()
            is_named = not low.startswith("total") and "all india" not in low
            if not has_figures:
                # Heading for the rows that follow
                flush(heading or last_label)
                heading = label
                last_label = label
            elif heading:
                # Subtotal closing an open heading's group
                flush(heading)
                heading = None
            elif is_named and after_total:
                # Heading-style area (groups end in "Total"): rows between the
                # last Total and this label are standalone HQs, and the label
                # heads the rows that follow.
                for d in pending:
                    d["region"] = d["hq"] or "Other"
                pending.clear()
                heading = label
            else:
                # Footer-style subtotal naming the rows above it
                flush(label if is_named else last_label)
            if is_named:
                last_label = label
            after_total = not is_named and has_figures
            continue

        if not name and not has_figures:
            continue  # empty territory placeholder (e.g. "Navi mumbai")

        hq = s0 or prev_hq  # rows with a blank HQ cell continue the HQ above
        prev_hq = hq
        total = month_to_date(weeks)
        ach = round(total / target * 100, 1) if (target and total is not None) else None
        doc = {
            "id": str(uuid.uuid4()),
            "month": month,
            "region": None,
            "hq": hq,
            "be_name": name or None,
            "doj": parse_excel_date(g(2)),
            "target": target,
            "w1": weeks[0], "w2": weeks[1], "w3": weeks[2], "w4": weeks[3],
            "sales_total": total,
            "achievement_pct": ach,
        }
        docs.append(doc)
        pending.append(doc)
    flush(heading or last_label)
    apply_current_week(docs)
    return docs


PERF_COLLECTIONS = {"brand": "brand_performance", "territory": "territory_performance",
                    "management": "management_dashboard"}


# ------------------- PowerPoint performance sheets -------------------
# Performance decks are sometimes shared as PowerPoint slides (one table per
# slide) instead of Excel. These adapters make a PPTX file look like an
# openpyxl workbook/worksheet — same .sheetnames / wb[name] / ws.iter_rows()
# surface — so it can flow through the exact same detect_perf_type /
# parse_brand_sheet / parse_territory_sheet / parse_mgmt_sheet logic as Excel.
class _RowsSheet:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True, max_row=None):
        rows = self._rows[:max_row] if max_row else self._rows
        for r in rows:
            yield r


class _RowsWorkbook:
    def __init__(self, sheets: dict):
        self._sheets = sheets

    @property
    def sheetnames(self):
        return list(self._sheets.keys())

    def __getitem__(self, name):
        return self._sheets[name]


def _pptx_slide_table_rows(table) -> list:
    rows = []
    for row in table.rows:
        # Normalize python-pptx's "" empty cells to None to match openpyxl's
        # semantics, since every downstream parser checks `is None`.
        rows.append(tuple((cell.text.strip() or None) for cell in row.cells))
    return rows


def load_perf_workbook(filename: str, contents: bytes):
    """Load an Excel or PowerPoint performance file into a workbook-like object."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        try:
            return load_workbook(filename=BytesIO(contents), data_only=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the Excel file. Please check the format.")
    if name.endswith(".pptx"):
        try:
            from pptx import Presentation
        except ImportError:
            raise HTTPException(status_code=400, detail="PowerPoint support is not available on this server.")
        try:
            prs = Presentation(BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the PowerPoint file. Please check the format.")
        sheets = {}
        for idx, slide in enumerate(prs.slides, start=1):
            texts = []
            title_shape = slide.shapes.title
            if title_shape is not None and title_shape.has_text_frame:
                t = title_shape.text_frame.text.strip()
                if t:
                    texts.append(t)
            for shape in slide.shapes:
                if shape.has_text_frame and shape is not title_shape:
                    t = shape.text_frame.text.strip()
                    if t:
                        texts.append(t)
            tables = [_pptx_slide_table_rows(shape.table) for shape in slide.shapes if shape.has_table]
            if not tables:
                continue
            base_name = " ".join(texts) if texts else f"Slide {idx}"
            for t_idx, rows in enumerate(tables):
                key = base_name if t_idx == 0 else f"{base_name} ({t_idx + 1})"
                suffix = 1
                unique_key = key
                while unique_key in sheets:
                    suffix += 1
                    unique_key = f"{key} #{suffix}"
                sheets[unique_key] = _RowsSheet(rows)
        return _RowsWorkbook(sheets)
    raise HTTPException(status_code=400, detail="Only .xlsx Excel or .pptx PowerPoint files are supported")


@api_router.post("/performance/upload")
async def upload_performance(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm", ".pptx")):
        raise HTTPException(status_code=400, detail="Only .xlsx Excel or .pptx PowerPoint files are supported")
    contents = await file.read()
    wb = load_perf_workbook(file.filename, contents)

    ptype = detect_perf_type(wb)
    if ptype is None:
        raise HTTPException(
            status_code=400,
            detail="Could not recognize this sheet. Supported: Brand Performance, Territory Performance, Management Dashboard, or the monthly Task sheet (use Task upload for that).",
        )

    collection = db[PERF_COLLECTIONS[ptype]]
    now = datetime.now(timezone.utc).isoformat()
    months_parsed = []
    total_inserted = 0
    for sn in wb.sheetnames:
        ws = wb[sn]
        month = resolve_sheet_month(ws, sn, file.filename or "")
        if month is None:
            continue
        if ptype == "brand":
            docs = parse_brand_sheet(ws, month)
        elif ptype == "territory":
            docs = parse_territory_sheet(ws, month)
        else:
            doc = parse_mgmt_sheet(ws, month)
            docs = [doc] if doc else []
        if not docs:
            continue
        for d in docs:
            d["created_at"] = now
        await collection.delete_many({"month": month})
        await collection.insert_many([dict(d) for d in docs])
        months_parsed.append(month)
        total_inserted += len(docs)

    if total_inserted == 0:
        raise HTTPException(status_code=400, detail="No data rows could be parsed from this file")
    return {"type": ptype, "months": sorted(set(months_parsed)), "inserted_count": total_inserted,
            "filename": file.filename}


@api_router.get("/performance/months")
async def performance_months(user: dict = Depends(require_feature("performance"))):
    out = {}
    all_months = set()
    for key, coll in PERF_COLLECTIONS.items():
        months = await db[coll].distinct("month")
        out[key] = sorted(months, reverse=True)
        all_months.update(months)
    out["all"] = sorted(all_months, reverse=True)
    return out


@api_router.get("/performance/brands")
async def performance_brands(month: Optional[str] = None, user: dict = Depends(require_feature("performance"))):
    if not month:
        months = await db.brand_performance.distinct("month")
        if not months:
            return {"month": None, "items": []}
        month = sorted(months, reverse=True)[0]
    items = await db.brand_performance.find({"month": month}, {"_id": 0}).to_list(500)
    items.sort(key=lambda x: -(x.get("sales_total") or 0))
    return {"month": month, "items": items}


@api_router.get("/performance/territories")
async def performance_territories(month: Optional[str] = None, user: dict = Depends(require_feature("performance"))):
    if not month:
        months = await db.territory_performance.distinct("month")
        if not months:
            return {"month": None, "regions": []}
        month = sorted(months, reverse=True)[0]
    items = await db.territory_performance.find({"month": month}, {"_id": 0}).to_list(1000)
    regions = {}
    for it in items:
        regions.setdefault(it.get("region") or "Other", []).append(it)
    out = []
    for region, its in regions.items():
        target = sum(i.get("target") or 0 for i in its)
        sales = sum(i.get("sales_total") or 0 for i in its)
        out.append({
            "region": region,
            "items": its,
            "target_total": round(target, 2),
            "sales_total": round(sales, 2),
            "achievement_pct": round(sales / target * 100, 1) if target else None,
        })
    out.sort(key=lambda r: -r["sales_total"])
    return {"month": month, "regions": out}


@api_router.get("/performance/management")
async def performance_management(month: Optional[str] = None, user: dict = Depends(require_feature("performance"))):
    if not month:
        months = await db.management_dashboard.distinct("month")
        if not months:
            return {"month": None, "metrics": None}
        month = sorted(months, reverse=True)[0]
    doc = await db.management_dashboard.find_one({"month": month}, {"_id": 0})
    return {"month": month, "metrics": (doc or {}).get("metrics")}


@api_router.get("/performance/territories/trend")
async def territories_trend(user: dict = Depends(require_feature("performance"))):
    """Region target/sales across every uploaded month (period-wise trend)."""
    items = await db.territory_performance.find({}, {"_id": 0}).to_list(5000)
    months = sorted({i["month"] for i in items})
    regions = {}
    for it in items:
        reg = it.get("region") or "Other"
        by = regions.setdefault(reg, {})
        cell = by.setdefault(it["month"], {"target": 0.0, "sales": 0.0})
        cell["target"] += it.get("target") or 0
        cell["sales"] += it.get("sales_total") or 0
    out = []
    for reg, by in regions.items():
        series = []
        for m in months:
            c = by.get(m)
            tgt = round(c["target"], 2) if c else None
            sal = round(c["sales"], 2) if c else None
            series.append({"month": m, "target": tgt, "sales": sal,
                           "achievement_pct": round(sal / tgt * 100, 1) if (tgt and sal is not None) else None})
        out.append({"region": reg, "series": series})
    out.sort(key=lambda r: r["region"])
    return {"months": months, "regions": out}


MGMT_NUMERIC_KEYS = ["primary_sales", "secondary_sales", "run_rate", "active_doctors", "new_prescribers"]


@api_router.get("/performance/management/trend")
async def management_trend(user: dict = Depends(require_feature("performance"))):
    """Each numeric management metric across every uploaded month."""
    docs = await db.management_dashboard.find({}, {"_id": 0}).to_list(1000)
    months = sorted({d["month"] for d in docs})
    by_month = {d["month"]: (d.get("metrics") or {}) for d in docs}
    metrics = {}
    for k in MGMT_NUMERIC_KEYS:
        series = []
        present = False
        for m in months:
            mt = by_month.get(m, {}).get(k)
            val = None
            if mt:
                val = mt.get("total")
                if val is None:
                    weeks = [w for w in (mt.get("weeks") or []) if isinstance(w, (int, float))]
                    val = weeks[-1] if weeks else None
                if val is not None:
                    present = True
            series.append({"month": m, "value": val})
        if present:
            metrics[k] = series
    return {"months": months, "metrics": metrics}


async def compute_brand_growth() -> dict:
    items = await db.brand_performance.find({}, {"_id": 0}).to_list(2000)
    months = sorted({i["month"] for i in items})
    brands = {}
    for i in items:
        key = i["brand"].strip().upper()
        brands.setdefault(key, {"brand": i["brand"].strip(), "by_month": {}})["by_month"][i["month"]] = i
    out = []
    for b in brands.values():
        series = []
        prev = None
        for m in months:
            it = b["by_month"].get(m)
            sales = it.get("sales_total") if it else None
            growth = None
            if sales is not None and prev not in (None, 0):
                growth = round((sales - prev) / prev * 100, 1)
            series.append({
                "month": m,
                "sales": sales,
                "target": it.get("target") if it else None,
                "growth_pct": growth,
            })
            if sales is not None:
                prev = sales
        vals = [s["sales"] for s in series if s["sales"] is not None]
        overall = round((vals[-1] - vals[0]) / vals[0] * 100, 1) if len(vals) >= 2 and vals[0] else None
        out.append({
            "brand": b["brand"],
            "series": series,
            "overall_growth_pct": overall,
            "latest_sales": vals[-1] if vals else None,
        })
    out.sort(key=lambda x: -(x["latest_sales"] or 0))
    return {"months": months, "brands": out}


@api_router.get("/performance/growth")
async def performance_growth(user: dict = Depends(require_feature("performance"))):
    return await compute_brand_growth()


# ------------------- Meta / filters -------------------
@api_router.get("/meta/filters")
async def meta_filters(user: dict = Depends(get_current_user)):
    tasks = visible_tasks(user, await db.tasks.find(
        {}, {"_id": 0, "hq": 1, "assignee": 1, "role": 1, "activity_category": 1,
             "frequency": 1, "created_by": 1}).to_list(10000))

    def distinct(key):
        return list({t[key] for t in tasks if t.get(key)})

    hqs = distinct("hq")
    assignees = distinct("assignee")
    roles = distinct("role")
    activity_categories = distinct("activity_category")
    frequencies = distinct("frequency")
    frequencies.sort(key=lambda f: FREQUENCIES.index(f) if f in FREQUENCIES else 99)
    return {"hqs": sorted(hqs), "assignees": sorted(assignees), "roles": sorted(roles),
            "activity_categories": sorted(activity_categories), "frequencies": frequencies,
            "frequency_labels": FREQUENCY_LABELS,
            "categories": CATEGORIES, "statuses": STATUSES, "heads": HEADS}


# ------------------- Dashboard & Reports -------------------
def summarize(tasks: List[dict]):
    total = len(tasks)
    completed = sum(1 for t in tasks if t["status"] == "completed")
    in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
    pending = sum(1 for t in tasks if t["status"] == "pending")
    today = utc_today().isoformat()
    overdue = sum(1 for t in tasks if t.get("due_date") and t["due_date"] < today and t["status"] != "completed")
    rate = round(completed / total * 100, 1) if total else 0.0
    return {"total": total, "completed": completed, "in_progress": in_progress,
            "pending": pending, "overdue": overdue, "completion_rate": rate}


def group_summary(tasks: List[dict], key: str):
    groups = {}
    for t in tasks:
        k = t.get(key) or "Unassigned"
        groups.setdefault(k, []).append(t)
    out = []
    for name, items in groups.items():
        s = summarize(items)
        out.append({"name": name, **s})
    out.sort(key=lambda x: (-x["total"], x["name"]))
    return out


def sales_summary(tasks: List[dict]):
    sales_tasks = [t for t in tasks if t["category"] in ("sales_collection", "target")]
    target_total = sum(t.get("target_amount") or 0 for t in sales_tasks)
    collected_total = sum(t.get("collected_amount") or 0 for t in sales_tasks)
    pct = round(collected_total / target_total * 100, 1) if target_total else 0.0
    return {"target_total": target_total, "collected_total": collected_total,
            "achievement_pct": pct, "count": len(sales_tasks)}


@api_router.get("/dashboard")
async def dashboard(user: dict = Depends(require_feature("dashboard"))):
    start, end = period_range("month")
    month_tasks = visible_tasks(user, await db.tasks.find(
        {"due_date": {"$gte": start, "$lte": end}}, {"_id": 0, "photos": 0}).to_list(5000))
    today = utc_today().isoformat()
    # Undated daily tasks recur every day; dated ones (e.g. a plan's daily
    # doctor message) belong only to their own day.
    todays = [t for t in month_tasks if t.get("due_date") == today or
              (t["frequency"] == "daily" and not t.get("start_date") and t["status"] != "completed")][:10]
    recent = visible_tasks(user, await db.tasks.find(
        {}, {"_id": 0, "photos": 0}).sort("created_at", -1).to_list(200))[:5]
    return {
        "kpis": summarize(month_tasks),
        "sales": sales_summary(month_tasks),
        "todays_tasks": todays,
        "recent_tasks": recent,
        "period": {"start": start, "end": end},
    }


HEAD_LABELS = {"company": "Company", "scientific_inputs": "Scientific Inputs",
               "engagement": "Engagement", "Unassigned": "Unassigned"}


async def build_report(period: str, user: dict) -> dict:
    if period not in ("week", "month", "quarter"):
        period = "month"
    start, end = period_range(period)
    tasks = visible_tasks(user, await db.tasks.find(
        {"due_date": {"$gte": start, "$lte": end}}, {"_id": 0, "photos": 0}).to_list(5000))
    return {
        "period": period,
        "range": {"start": start, "end": end},
        "kpis": summarize(tasks),
        "by_hq": group_summary(tasks, "hq"),
        "by_assignee": group_summary(tasks, "assignee"),
        "by_role": group_summary(tasks, "role"),
        "by_frequency": group_summary(tasks, "frequency"),
        "by_activity_category": group_summary(tasks, "activity_category"),
        "by_head": group_summary(tasks, "head"),
        "sales": sales_summary(tasks),
    }


@api_router.get("/reports")
async def reports(period: str = "month", user: dict = Depends(require_feature("reports"))):
    return await build_report(period, user)


@api_router.get("/reports/pdf")
async def reports_pdf(period: str = "month", user: dict = Depends(require_feature("reports"))):
    from fastapi.responses import Response
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    data = await build_report(period, user)
    kpis = data["kpis"]
    sales = data["sales"]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Surishi Marketing Report - {period.title()}",
    )
    styles = getSampleStyleSheet()
    brand = rl.HexColor("#0055A4")
    gold = rl.HexColor("#C98F12")
    title_style = ParagraphStyle("T", parent=styles["Title"], textColor=brand, fontSize=18, spaceAfter=2)
    sub_style = ParagraphStyle("S", parent=styles["Normal"], textColor=rl.HexColor("#64748B"), fontSize=10)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=brand, fontSize=13, spaceBefore=14, spaceAfter=6)

    period_label = {"week": "Weekly", "month": "Monthly", "quarter": "Quarterly"}[data["period"]]
    story = [
        Paragraph("Surishi Pharmaceuticals", title_style),
        Paragraph(f"Marketing Execution — {period_label} Report", styles["Heading3"]),
        Paragraph(
            f"Period: {data['range']['start']} to {data['range']['end']} &nbsp;·&nbsp; "
            f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')} &nbsp;·&nbsp; surishi.in",
            sub_style,
        ),
        Spacer(1, 10),
    ]

    def styled_table(rows, col_widths=None, header_bg=brand):
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, rl.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl.white, rl.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    story.append(Paragraph("Key Metrics", h2))
    story.append(styled_table([
        ["Total Tasks", "Completed", "In Progress", "Pending", "Overdue", "Completion %"],
        [str(kpis["total"]), str(kpis["completed"]), str(kpis["in_progress"]),
         str(kpis["pending"]), str(kpis["overdue"]), f"{kpis['completion_rate']}%"],
    ]))

    story.append(Paragraph("Sales Collection vs Target", h2))
    story.append(styled_table([
        ["Target Total", "Collected Total", "Achievement %", "Sales Items"],
        [f"Rs. {sales['target_total']:,.0f}", f"Rs. {sales['collected_total']:,.0f}",
         f"{sales['achievement_pct']}%", str(sales["count"])],
    ], header_bg=gold))

    for key, label in (("by_activity_category", "Activity Category-wise Performance"),
                       ("by_head", "Activity Head-wise Performance"), ("by_hq", "HQ-wise Performance"),
                       ("by_assignee", "Assignee-wise Performance"),
                       ("by_role", "Role-wise Performance"), ("by_frequency", "Frequency-wise Performance")):
        rows = data.get(key) or []
        if not rows:
            continue
        story.append(Paragraph(label, h2))
        table_rows = [["Name", "Total", "Completed", "In Progress", "Pending", "Overdue", "Rate"]]
        for r in rows:
            if key == "by_head":
                display = HEAD_LABELS.get(r["name"], r["name"])
            elif key == "by_frequency":
                display = FREQUENCY_LABELS.get(r["name"], r["name"])
            else:
                display = r["name"]
            table_rows.append([
                Paragraph(str(display), styles["Normal"]),
                str(r["total"]), str(r["completed"]), str(r["in_progress"]),
                str(r["pending"]), str(r["overdue"]), f"{r['completion_rate']}%",
            ])
        story.append(styled_table(table_rows, col_widths=[60 * mm, None, None, None, None, None, None]))

    # ---------- Performance data (latest month) ----------
    perf_months = await db.brand_performance.distinct("month")
    month_label_map = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                       7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

    def pm_label(m):
        y, mo = m.split("-")
        return f"{month_label_map[int(mo)]} {y}"

    if perf_months:
        pm = max(perf_months)
        brand_rows = await db.brand_performance.find({"month": pm}, {"_id": 0}).to_list(200)
        brand_rows.sort(key=lambda x: -(x.get("sales_total") or 0))
        if brand_rows:
            story.append(Paragraph(f"Brand Performance — {pm_label(pm)}", h2))
            table_rows = [["Brand", "Target", "Sales", "Ach %", "Top Territory", "Low Territory"]]
            for b in brand_rows:
                table_rows.append([
                    Paragraph(b["brand"], styles["Normal"]),
                    f"{b['target']:,.0f}" if b.get("target") else "-",
                    f"{b['sales_total']:,.0f}" if b.get("sales_total") is not None else "-",
                    f"{b['achievement_pct']}%" if b.get("achievement_pct") is not None else "-",
                    Paragraph(str(b.get("top_territory") or "-"), styles["Normal"]),
                    Paragraph(str(b.get("low_territory") or "-"), styles["Normal"]),
                ])
            story.append(styled_table(table_rows, col_widths=[38 * mm, 16 * mm, 16 * mm, 14 * mm, 45 * mm, 45 * mm], header_bg=gold))

        growth = await compute_brand_growth()
        if len(growth["months"]) >= 2:
            story.append(Paragraph(
                f"Brand Growth — Month over Month ({pm_label(growth['months'][0])} → {pm_label(growth['months'][-1])})", h2))
            table_rows = [["Brand"] + [pm_label(m) for m in growth["months"]] + ["Overall"]]
            for b in growth["brands"]:
                row_cells = [Paragraph(b["brand"], styles["Normal"])]
                for s in b["series"]:
                    cell_txt = f"{s['sales']:,.0f}" if s["sales"] is not None else "-"
                    if s["growth_pct"] is not None:
                        cell_txt += f" ({'+' if s['growth_pct'] >= 0 else ''}{s['growth_pct']}%)"
                    row_cells.append(cell_txt)
                overall = b["overall_growth_pct"]
                row_cells.append(f"{'+' if overall is not None and overall >= 0 else ''}{overall}%" if overall is not None else "-")
                table_rows.append(row_cells)
            story.append(styled_table(table_rows, col_widths=[40 * mm] + [None] * (len(growth["months"]) + 1)))

    terr_months = await db.territory_performance.distinct("month")
    if terr_months:
        tm = max(terr_months)
        terr_rows = await db.territory_performance.find({"month": tm}, {"_id": 0}).to_list(1000)
        regions = {}
        for it in terr_rows:
            regions.setdefault(it.get("region") or "Other", []).append(it)
        if regions:
            story.append(Paragraph(f"Territory Performance by Region — {pm_label(tm)}", h2))
            table_rows = [["Region", "HQs", "Target (L)", "Sales (L)", "Ach %"]]
            region_list = []
            for region, its in regions.items():
                tgt = sum(i.get("target") or 0 for i in its)
                sal = sum(i.get("sales_total") or 0 for i in its)
                region_list.append((region, len(its), tgt, sal))
            region_list.sort(key=lambda x: -x[3])
            for region, n, tgt, sal in region_list:
                table_rows.append([
                    Paragraph(region, styles["Normal"]), str(n),
                    f"{tgt:,.2f}", f"{sal:,.2f}",
                    f"{sal / tgt * 100:.0f}%" if tgt else "-",
                ])
            story.append(styled_table(table_rows, col_widths=[55 * mm, None, None, None, None]))

    mgmt_months = await db.management_dashboard.distinct("month")
    if mgmt_months:
        mm_ = max(mgmt_months)
        mdoc = await db.management_dashboard.find_one({"month": mm_}, {"_id": 0})
        metrics = (mdoc or {}).get("metrics") or {}
        numeric_labels = [("primary_sales", "Total Primary Sales (Lacs)"),
                          ("secondary_sales", "Total Secondary Sales (Lacs)"),
                          ("active_doctors", "Active Doctors"),
                          ("new_prescribers", "New Prescribers")]
        rows_num = []
        for key, label in numeric_labels:
            m = metrics.get(key)
            if not m:
                continue
            weeks = m.get("weeks") or [None] * 4
            rows_num.append([label] + [f"{w:,.2f}".rstrip("0").rstrip(".") if isinstance(w, (int, float)) else "-" for w in weeks])
        if rows_num:
            story.append(Paragraph(f"Management Dashboard — {pm_label(mm_)}", h2))
            story.append(styled_table([["Metric", "W1", "W2", "W3", "W4"]] + rows_num,
                                      col_widths=[60 * mm, None, None, None, None]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    filename = f"surishi_{period}_report_{data['range']['start']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.get("/")
async def root():
    return {"message": "Surishi Pharma Marketing Execution API"}


# ------------------- Seed demo users -------------------
DEMO_USERS = [
    {"name": "Marketing Head", "email": "head@surishi.com", "role": "marketing_head"},
    {"name": "Deputy Marketing Head", "email": "deputy@surishi.com", "role": "marketing_deputy_head"},
    {"name": "Product Executive", "email": "pe@surishi.com", "role": "product_executive"},
    {"name": "General Manager", "email": "gm@surishi.com", "role": "general_manager"},
    {"name": "CEO", "email": "ceo@surishi.com", "role": "ceo"},
    {"name": "Chairman", "email": "chairman@surishi.in", "role": "chairman"},
    {"name": "AGM", "email": "agm@surishi.com", "role": "agm"},
    {"name": "Business Manager", "email": "bm@surishi.com", "role": "business_manager"},
]
DEMO_PASSWORD = "Surishi@123"


@app.on_event("startup")
async def seed_users():
    for u in DEMO_USERS:
        existing = await db.users.find_one({"email": u["email"]})
        if not existing:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "name": u["name"],
                "email": u["email"],
                "role": u["role"],
                "hq": None,
                "password_hash": pwd_hash.hash(DEMO_PASSWORD),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    logger.info("Demo users seeded")
    await seed_task_sheet()
    await recompute_perf_month_to_date()


PERF_MTD_MARKER = "perf_mtd_v1"


async def recompute_perf_month_to_date():
    """One-off fix for brand/territory rows stored before sales were read as
    month-to-date: recompute sales_total/achievement_pct from the stored weeks."""
    marker = await db.app_meta.find_one({"key": "perf_mtd"})
    if marker and marker.get("version") == PERF_MTD_MARKER:
        return
    for coll in (db.brand_performance, db.territory_performance):
        docs = await coll.find({}, {"_id": 0}).to_list(20000)
        by_month = {}
        for d in docs:
            by_month.setdefault(d.get("month"), []).append(d)
        for month_docs in by_month.values():
            apply_current_week(month_docs)
            for d in month_docs:
                await coll.update_one({"id": d["id"]}, {"$set": {
                    "sales_total": d["sales_total"], "achievement_pct": d["achievement_pct"]}})
    await db.app_meta.update_one(
        {"key": "perf_mtd"}, {"$set": {"key": "perf_mtd", "version": PERF_MTD_MARKER}}, upsert=True)
    logger.info("Performance month-to-date totals recomputed")


SEED_MARKER = "task_sheet_v1"


async def seed_task_sheet():
    """Load the standard task sheet's tasks once, the first time the app runs.
    Opt-in via SEED_TASK_SHEET=1 (default off, so the app starts empty).
    Guarded by a marker in app_meta so restarts never duplicate, and so tasks
    the admin later deletes do not reappear."""
    if os.environ.get("SEED_TASK_SHEET", "").lower() not in ("1", "true", "yes"):
        return
    marker = await db.app_meta.find_one({"key": "seed_task_sheet"})
    if marker and marker.get("version") == SEED_MARKER:
        return
    path = ROOT_DIR / "seed" / "task_sheet.json"
    if not path.exists():
        return
    try:
        import json as _json
        rows = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not read task sheet seed: %s", e)
        return
    system_user = await db.users.find_one({"email": "chairman@surishi.in"}) \
        or await db.users.find_one({"role": "chairman"})
    created_by = system_user["id"] if system_user else "system"
    docs = []
    for r in rows:
        data = {
            "title": r.get("title"),
            "description": r.get("description"),
            "assignee": r.get("assignee"),
            "activity_category": r.get("activity_category"),
            "frequency": norm_frequency(r.get("frequency")),
            "frequency_label": r.get("frequency"),
            "due_date": r.get("due_date"),
            "reporting_due_date": r.get("reporting_due_date"),
        }
        doc = task_doc(data, created_by, source="sheet")
        doc["seed"] = SEED_MARKER
        docs.append(doc)
    if docs:
        await db.tasks.insert_many([dict(d) for d in docs])
    await db.app_meta.update_one(
        {"key": "seed_task_sheet"},
        {"$set": {"key": "seed_task_sheet", "version": SEED_MARKER,
                  "count": len(docs), "seeded_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    logger.info("Task sheet seeded: %d tasks", len(docs))


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
