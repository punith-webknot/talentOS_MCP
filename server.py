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


# ---------------------------------------------------------------------------
# Ask Form
# ---------------------------------------------------------------------------

@mcp.tool()
def ask_form(
    emp_ids: list[str],
    form_type: str = "SLOTS",
) -> dict[str, Any]:
    """Send a slot-selection form link email to one or more employees.

    Currently only SLOTS is supported. Mail is sent in the background after the
    response returns. Form links are valid for 24 hours.

    Args:
        emp_ids: At least one employee ID, e.g. ["EMP028", "EMP200"].
        form_type: Form type; defaults to "SLOTS". REVIEW is not implemented yet.

    Returns per-employee results with status SUCCESS or FAILED. SUCCESS messages
    include "New link sent" or "Existing link resent". FAILED messages include
    "Employee not found", "Invalid or missing email", or "Email service not configured".
    """
    payload: dict[str, Any] = {"emp_ids": emp_ids, "type": form_type}
    result = api_request("POST", "/ask-form", json_data=payload)
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


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"TalentOS MCP server starting on port {port}")

    if TALENTOS_API_BASE_URL:
        print(f"Calling talentOS Backend API at {TALENTOS_API_BASE_URL}/api/v1")
    else:
        print(f"WARNING: {CONFIG_ERROR}")

    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)