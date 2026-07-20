import atexit
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables directly
load_dotenv()

TALENTOS_API_BASE_URL = os.environ.get("TALENTOS_API_BASE_URL", "").rstrip("/")
API_TIMEOUT = int(os.environ.get("TALENTOS_API_TIMEOUT", "30"))
CONFIG_ERROR = "TALENTOS_API_BASE_URL is not set"

mcp = FastMCP("TalentOS")
_client: httpx.Client | None = None

if TALENTOS_API_BASE_URL:
    _client = httpx.Client(
        base_url=f"{TALENTOS_API_BASE_URL}/api/v1",
        timeout=API_TIMEOUT,
    )
    atexit.register(_client.close)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return body.get("message") or body.get("detail") or str(body)
    except ValueError:
        pass
    return response.text or f"HTTP {response.status_code}"


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and result.get("status") == "error"


def _success(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return {**result, "status": "success"}
    return {"status": "success", "data": result}


def api_request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_data: dict | None = None,
) -> Any:
    if _client is None:
        return {"status": "error", "message": CONFIG_ERROR}
    try:
        response = _client.request(method, path, params=params, json=json_data)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {
                "status": "error",
                "message": "Invalid JSON in API response",
            }
    except httpx.HTTPStatusError as exc:
        return {
            "status": "error",
            "http_status": exc.response.status_code,
            "message": _error_message(exc.response),
        }
    except httpx.RequestError as exc:
        return {"status": "error", "message": f"Failed to reach talentOS Backend API: {exc}"}


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@mcp.tool()
def get_benched_candidates(designation: str) -> dict[str, Any]:
    """Fetch employees currently on the bench for a given designation."""
    result = api_request("GET", "/users/benched", params={"designation": designation})
    if _is_error(result):
        return result
    return _success(result)


# ---------------------------------------------------------------------------
# Designations
# ---------------------------------------------------------------------------

@mcp.tool()
def get_all_designations() -> dict[str, Any]:
    """List all unique designation names in the organization."""
    result = api_request("GET", "/designations")
    if _is_error(result):
        return result
    if isinstance(result, list):
        return _success({"designations": result})
    return _success(result)


@mcp.tool()
def get_designation_detail(name: str) -> dict[str, Any]:
    """Get designation details including band level and KPIs."""
    result = api_request("GET", "/designation", params={"name": name})
    if _is_error(result):
        return result
    return _success(result)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@mcp.tool()
def get_all_jobs(
    q: str | None = None,
    department: str | None = None,
    location: str | None = None,
    job_type: str | None = None,
    is_active: bool | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    """List job listings with optional search, filters, and pagination.

    All parameters are optional. Search with q (title, department, or location),
    filter by department, location, type, or active status, narrow by created date
    range (ISO 8601), and paginate with page (default 1) and per_page (default 10, max 50).
    """
    params: dict[str, Any] = {}
    if q is not None:
        params["q"] = q
    if department is not None:
        params["department"] = department
    if location is not None:
        params["location"] = location
    if job_type is not None:
        params["type"] = job_type
    if is_active is not None:
        params["is_active"] = is_active
    if created_from is not None:
        params["created_from"] = created_from
    if created_to is not None:
        params["created_to"] = created_to
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page

    result = api_request("GET", "/hiring-requests/", params=params or None)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_job_by_id(hiring_request_id: str) -> dict[str, Any]:
    """Fetch a single job listing by its unique ID."""
    result = api_request("GET", f"/hiring-requests/{hiring_request_id}")
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def create_job(
    title: str,
    department: str,
    location: str,
    job_type: str,
    description: str,
    requirements: list[str],
    benefits: list[str],
    is_active: bool,
    custom_evaluation_criteria: str,
) -> dict[str, Any]:
    """Create and publish a new job posting."""
    payload = {
        "title": title,
        "department": department,
        "location": location,
        "type": job_type,
        "description": description,
        "requirements": requirements,
        "benefits": benefits,
        "is_active": is_active,
        "custom_evaluation_criteria": custom_evaluation_criteria,
    }
    result = api_request("POST", "/hiring-requests/", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def update_job(
    hiring_request_id: str,
    title: str,
    department: str,
    location: str,
    job_type: str,
    description: str,
    requirements: list[str],
    benefits: list[str],
    is_active: bool,
    custom_evaluation_criteria: str,
) -> dict[str, Any]:
    """Update an existing job posting. All fields must be provided, even if only one is changing."""
    payload = {
        "title": title,
        "department": department,
        "location": location,
        "type": job_type,
        "description": description,
        "requirements": requirements,
        "benefits": benefits,
        "is_active": is_active,
        "custom_evaluation_criteria": custom_evaluation_criteria,
    }
    result = api_request("PUT", f"/hiring-requests/{hiring_request_id}", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def delete_job(hiring_request_id: str) -> dict[str, Any]:
    """Permanently delete a job posting by its unique ID."""
    result = api_request("DELETE", f"/hiring-requests/{hiring_request_id}")
    if _is_error(result):
        return result
    return _success(result)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@mcp.tool()
def list_applications(
    job_id: str,
    status: str | None = None,
    schedule: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List job applications for a job with optional filters.

    job_id is required. Optional filters: evaluation status (e.g. SHORTLISTED,
    REJECTED), schedule (scheduled or unscheduled), ATS score range (0-100),
    created date range (ISO 8601), and pagination (limit 1-100, offset).
    """
    params: dict[str, Any] = {"job_id": job_id}
    if status is not None:
        params["status"] = status
    if schedule is not None:
        params["schedule"] = schedule
    if min_score is not None:
        params["min_score"] = min_score
    if max_score is not None:
        params["max_score"] = max_score
    if date_from is not None:
        params["date_from"] = date_from
    if date_to is not None:
        params["date_to"] = date_to
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset

    result = api_request("GET", "/applications/", params=params)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_application_by_id(application_id: str) -> dict[str, Any]:
    """Fetch a job application by its unique ID.

    Returns candidate details, resume URL, evaluation summary, fit score,
    application status, and related job metadata.
    """
    result = api_request("GET", f"/applications/{application_id}")
    if _is_error(result):
        return result
    return _success(result)


# ===========================================================================
# Phase: Employees (directory)
# ===========================================================================

@mcp.tool()
def get_users(
    q: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
    slots_info: bool | None = None,
) -> dict[str, Any]:
    """Search and paginate employee users, optionally with slot availability.

    Return 20 per page by default and ask if the user wants to see more.

    Args:
        q: Search query — matches name, email, or emp_id.
        page: Page number (default 1, min 1).
        per_page: Page size (default 20, min 1, max 100).
        slots_info: If true, includes slots_count and has_slots, sorted by
            slot count descending.
    """
    params: dict[str, Any] = {}
    if q is not None:
        params["q"] = q
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page
    if slots_info is not None:
        params["slotsInfo"] = slots_info

    result = api_request("GET", "/users/", params=params or None)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_user_by_emp_id(emp_id: str) -> dict[str, Any]:
    """Fetch a single employee by their employee ID string (e.g. EMP028).

    Returns 404 if emp_id is not found. slots_count and has_slots are always
    0/false in single-user lookup.
    """
    result = api_request("GET", f"/users/{emp_id}")
    if _is_error(result):
        return result
    return _success(result)


# ===========================================================================
# Phase: Slots (collect & view availability)
# ===========================================================================

@mcp.tool()
def ask_form(
    emp_ids: list[str],
    form_type: str = "SLOTS",
    round_id: str | None = None,
    candidate_id: int | None = None,
) -> dict[str, Any]:
    """Send a slot-selection or review form email to one or more employees.

    Default is SLOTS. Use form_type="REVIEW" with round_id and candidate_id to
    request interview reviews. Mail is sent in the background. Links valid 24h.

    Args:
        emp_ids: At least one employee ID.
        form_type: "SLOTS" (default) or "REVIEW".
        round_id: Required when form_type is "REVIEW" — round UUID.
        candidate_id: Required when form_type is "REVIEW" — candidate ID.

    Returns per-employee results with status SUCCESS or FAILED. SUCCESS messages
    include "New link sent", "Existing link resent", or "Review form sent".
    FAILED messages include "Employee not found", "Invalid or missing email",
    or "Employee is not an interviewer for this round".
    """
    payload: dict[str, Any] = {"emp_ids": emp_ids, "type": form_type}
    if round_id is not None:
        payload["round_id"] = round_id
    if candidate_id is not None:
        payload["candidate_id"] = candidate_id

    result = api_request("POST", "/ask-form", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_employee_slots(emp_ids: list[str]) -> dict[str, Any]:
    """Get available, future slots for one or more employees (batch).

    Unknown employee IDs are included with an empty slots list (no error).
    Only available slots are returned; past slots are excluded. Times are in IST.

    Args:
        emp_ids: At least one employee ID, e.g. ["EMP028", "EMP200"].

    Each slot has id (UUID), label (IST time range), and day ("Today", "Tomorrow",
    or a date like "08 Jul").
    """
    result = api_request(
        "GET",
        "/slots/employee",
        params={"emp_ids": emp_ids},
    )
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_employee_form_status(
    form_type: str,
    status: str,
    emp_ids: list[str] | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    """List employees filtered by their latest form of the given type and status.

    One row per employee (their most recent form for that type). SENT means not
    submitted; SUBMITTED means submitted; EXPIRED means the link expired.
    Works for both SLOTS and REVIEW forms.

    Args:
        form_type: Form type — "SLOTS" or "REVIEW".
        status: Form status — "SENT", "SUBMITTED", or "EXPIRED".
        emp_ids: Optional employee IDs to narrow results; omit for all employees.
        page: Page number (default 1, min 1).
        per_page: Page size (default 20, min 1, max 100).
    """
    params: dict[str, Any] = {"type": form_type, "status": status}
    if emp_ids is not None:
        params["emp_ids"] = emp_ids
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page

    result = api_request("GET", "/employees/form-status", params=params)
    if _is_error(result):
        return result
    return _success(result)


# ===========================================================================
# Phase: Scheduling (book & manage interviews)
# ===========================================================================

@mcp.tool()
def book_interview(
    round_name: str,
    slot_id: str,
    jd_id: str,
    candidate_id: int,
    interviewer_ids: list[int],
    create_google_meet: bool = True,
) -> dict[str, Any]:
    """Book an interview: create a round, assign interviewers, schedule a slot.

    Optionally creates a Google Meet link. Use when scheduling an interview for
    a candidate with a slot and interviewer(s).

    Args:
        round_name: Display name, e.g. "Technical Round 1".
        slot_id: The slot UUID to book.
        jd_id: Job description / hiring request UUID.
        candidate_id: Candidate ID.
        interviewer_ids: At least one employee user ID (numeric).
        create_google_meet: Whether to create a Google Meet link (default true).

    Returns interview id, round_id, slot_id, event_id, meet_link, and status
    SCHEDULED on success. Errors: 404 candidate/slot not found; 409 candidate
    finalized or slot unavailable.
    """
    payload: dict[str, Any] = {
        "round_name": round_name,
        "slot_id": slot_id,
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "interviewer_ids": interviewer_ids,
        "create_google_meet": create_google_meet,
    }
    result = api_request("POST", "/interviews/booking", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_interviews(
    status_filter: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    """List interviews with candidate, interviewer, position, schedule, and meeting link.

    Args:
        status_filter: "incoming" (future slots), "completed" (past slots),
            "cancelled", or omit for all non-cancelled.
        page: Page number (default 1, min 1).
        per_page: Page size (default 20, min 1, max 100).
    """
    params: dict[str, Any] = {}
    if status_filter is not None:
        params["status_filter"] = status_filter
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page

    result = api_request("GET", "/interviews", params=params or None)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_interview_detail(interview_id: str) -> dict[str, Any]:
    """Get full details for a single interview by UUID.

    Includes round, candidate, interviewer, slot schedule, meeting link, and
    status. Returns 404 if not found.
    """
    result = api_request("GET", f"/interviews/{interview_id}")
    if _is_error(result):
        return result
    return _success(result)


# ===========================================================================
# Phase: Review (rounds, ratings, verdicts)
# ===========================================================================

@mcp.tool()
def get_rounds(
    page: int | None = None,
    per_page: int | None = None,
    candidate_id: int | None = None,
    jd_id: str | None = None,
) -> dict[str, Any]:
    """List interview rounds with candidate, slot, and interviewer info.

    Ordered by created_at descending. Use when asking what rounds a candidate
    has been through.

    Args:
        page: Page number (default 1, min 1).
        per_page: Page size (default 20, min 1, max 100).
        candidate_id: Filter by candidate ID.
        jd_id: Filter by job / hiring request UUID.
    """
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page
    if candidate_id is not None:
        params["candidate_id"] = candidate_id
    if jd_id is not None:
        params["jd_id"] = jd_id

    result = api_request("GET", "/rounds", params=params or None)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def get_round_details(round_id: str) -> dict[str, Any]:
    """Get full details for a specific round: reviews, ratings, verdict, outcome.

    Includes candidate, slot, interviewer, and all reviews (AI, HR, or
    interviewer). Returns 404 if round not found.
    """
    result = api_request("GET", f"/rounds/{round_id}")
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def shortlist_round(round_id: str, remark: str = "") -> dict[str, Any]:
    """Shortlist a candidate for a round. Use when HR asks to shortlist this candidate.

    Args:
        round_id: The round UUID.
        remark: Optional remark for the shortlist decision.

    Returns the updated round (id, candidate_id, slot_id, jd_id, name,
    round_verdict, created_at, updated_at). Errors: 404 round not found;
    400 round has no candidate or candidate already finalized.
    """
    payload: dict[str, Any] = {"verdict": "shortlisted", "remark": remark}
    result = api_request("POST", f"/rounds/{round_id}/shortlist", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def reject_round(round_id: str, remark: str = "") -> dict[str, Any]:
    """Reject a candidate for a round. Use when HR asks to reject this candidate.

    WARNING: The candidate will be permanently moved out of the hiring pipeline.

    Args:
        round_id: The round UUID.
        remark: Optional remark for the reject decision.

    Returns the updated round with round_verdict "rejected". Errors: 404 round
    not found; 400 round has no candidate or candidate already finalized.
    """
    payload: dict[str, Any] = {"verdict": "rejected", "remark": remark}
    result = api_request("POST", f"/rounds/{round_id}/reject", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def set_final_verdict(candidate_id: int, verdict: str) -> dict[str, Any]:
    """Set the final hiring verdict for a candidate.

    Use when HR asks to update the final verdict of this candidate.

    WARNING: The candidate will be permanently moved out of the hiring pipeline.

    Args:
        candidate_id: The candidate / application ID.
        verdict: Final verdict — "SELECTED" or "REJECTED".

    Returns the evaluation response. Errors if the candidate is already
    finalized (e.g. "Candidate 1 already finalized with verdict SELECTED").
    """
    payload: dict[str, Any] = {"verdict": verdict}
    result = api_request(
        "PATCH",
        f"/applications/{candidate_id}/final-verdict",
        json_data=payload,
    )
    if _is_error(result):
        return result
    return _success(result)


# ===========================================================================
# Phase: Alerts (slot & review notifications)
# ===========================================================================

@mcp.tool()
def get_alerts(
    page: int | None = None,
    per_page: int | None = None,
    alert_type: str | None = None,
    is_read: bool | None = False,
) -> dict[str, Any]:
    """List alerts (slot submissions, review requests), paginated.

    Start with unread alerts (default). If the user wants read alerts too,
    pass is_read accordingly or omit filtering.

    Args:
        page: Page number (default 1, min 1).
        per_page: Page size (default 20, min 1, max 100).
        alert_type: Filter by "slots" or "reviews".
        is_read: Filter by read status. Defaults to false (unread). Pass true
            for read alerts. Omit (None) for all.
    """
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page
    if alert_type is not None:
        params["type"] = alert_type
    if is_read is not None:
        params["is_read"] = is_read

    result = api_request("GET", "/alerts/", params=params or None)
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def read_alert(alert_id: str) -> dict[str, Any]:
    """Mark an alert as read/resolved.

    Idempotent — calling again on an already-read alert returns the existing
    alert with no side effects.
    """
    result = api_request("PATCH", f"/alerts/{alert_id}/read")
    if _is_error(result):
        return result
    return _success(result)


@mcp.tool()
def notify_alert(
    user_id: int,
    form_type: str = "SLOTS",
    reminder: bool = True,
) -> dict[str, Any]:
    """Send a form notification or reminder email for slot submission or review.

    Args:
        user_id: Employee user ID (numeric).
        form_type: "SLOTS" (default) or "REVIEW".
        reminder: If true (default), resends the existing link when an active
            SENT form exists within 24h; if false, creates a new form.

    Returns message, detail (NEW_LINK_SENT or RESENT_EXISTING_LINK), and form_id.
    Errors: 429 rate-limited; 404 user not found.
    """
    payload: dict[str, Any] = {
        "user_id": user_id,
        "type": form_type,
        "reminder": reminder,
    }
    result = api_request("POST", "/forms/notify", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


# ===========================================================================
# Utility: Email
# ===========================================================================

@mcp.tool()
def send_mail(
    to_email: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> dict[str, Any]:
    """Send a custom email via SMTP (notifications, alerts, or any message).

    General-purpose mail for any purpose. If html is provided it takes
    precedence for rendering; body is used as plain-text fallback.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Plain text body.
        html: Optional HTML version of the body.
    """
    payload: dict[str, Any] = {
        "to_email": to_email,
        "subject": subject,
        "body": body,
    }
    if html is not None:
        payload["html"] = html

    result = api_request("POST", "/email/send", json_data=payload)
    if _is_error(result):
        return result
    return _success(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"TalentOS MCP server starting on port {port}")

    if TALENTOS_API_BASE_URL:
        print(f"Calling talentOS Backend API at {TALENTOS_API_BASE_URL}/api/v1")
    else:
        print(f"WARNING: {CONFIG_ERROR}")

    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)