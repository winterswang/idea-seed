"""Team protocols - shutdown and plan approval."""

import threading
import uuid

from agent.team import BUS


# Request trackers with thread-safe access
shutdown_requests: dict = {}
plan_requests: dict = {}
_tracker_lock = threading.Lock()


def handle_shutdown_request(teammate: str) -> str:
    """Send shutdown request to teammate. Returns request_id."""
    req_id = str(uuid.uuid4())[:8]
    with _tracker_lock:
        shutdown_requests[req_id] = {"target": teammate, "status": "pending"}

    BUS.send(
        "lead",
        teammate,
        "Please shut down gracefully.",
        "shutdown_request",
        {"request_id": req_id},
    )

    return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"


def handle_shutdown_response(
    req_id: str, approve: bool, reason: str = ""
) -> str:
    """Handle shutdown response from teammate."""
    with _tracker_lock:
        if req_id in shutdown_requests:
            shutdown_requests[req_id]["status"] = "approved" if approve else "rejected"

    return f"Shutdown {'approved' if approve else 'rejected'}"


def check_shutdown_status(req_id: str) -> dict:
    """Check status of shutdown request."""
    with _tracker_lock:
        return shutdown_requests.get(req_id, {"error": "not found"})


def submit_plan(from_name: str, plan: str) -> str:
    """Submit plan for approval. Returns request_id."""
    req_id = str(uuid.uuid4())[:8]
    with _tracker_lock:
        plan_requests[req_id] = {"from": from_name, "plan": plan, "status": "pending"}

    BUS.send(
        from_name,
        "lead",
        plan,
        "plan_approval",
        {"request_id": req_id, "plan": plan},
    )

    return f"Plan submitted (request_id={req_id}). Waiting for lead approval."


def approve_plan(
    req_id: str, approve: bool, feedback: str = ""
) -> str:
    """Approve or reject a plan. Returns status."""
    with _tracker_lock:
        req = plan_requests.get(req_id)

    if not req:
        return f"Error: Unknown plan request_id '{req_id}'"

    with _tracker_lock:
        req["status"] = "approved" if approve else "rejected"

    BUS.send(
        "lead",
        req["from"],
        feedback,
        "plan_approval_response",
        {"request_id": req_id, "approve": approve, "feedback": feedback},
    )

    return f"Plan {req['status']} for '{req['from']}'"


def get_plan_request(req_id: str) -> dict | None:
    """Get plan request details."""
    with _tracker_lock:
        return plan_requests.get(req_id)


# Protocol tool schemas for lead
PROTOCOL_TOOLS = [
    {
        "name": "shutdown_request",
        "description": "Request a teammate to shut down gracefully. Returns request_id for tracking.",
        "input_schema": {
            "type": "object",
            "properties": {"teammate": {"type": "string"}},
            "required": ["teammate"],
        },
    },
    {
        "name": "shutdown_response",
        "description": "Check the status of a shutdown request by request_id.",
        "input_schema": {
            "type": "object",
            "properties": {"request_id": {"type": "string"}},
            "required": ["request_id"],
        },
    },
    {
        "name": "plan_approval",
        "description": "Approve or reject a teammate's plan. Provide request_id + approve + optional feedback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "approve": {"type": "boolean"},
                "feedback": {"type": "string"},
            },
            "required": ["request_id", "approve"],
        },
    },
]
