"""Constants for Idea Seed."""

# Phase states
PHASE_REQUIREMENTS = "requirements"
PHASE_TECH_DESIGN = "tech_design"
PHASE_EXECUTION_PLAN = "execution_plan"
PHASE_PLANS = "plans"  # v2: Requirements → Plans → Tech-Spec
PHASE_DONE = "done"

# Execution mode
MODE_LEGACY = "legacy"
MODE_PLAN = "plan"

# Task status
TASK_STATUS_PENDING = "pending"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_VERIFICATION_FAILED = "verification_failed"
TASK_STATUS_BLOCKED = "blocked"

# Verification types
VERIFICATION_COMMAND_EXECUTION = "command_execution"
VERIFICATION_FILE_EXISTENCE = "file_existence"
VERIFICATION_COVERAGE_CHECK = "coverage_check"
VERIFICATION_MANUAL = "manual"
VERIFICATION_PHASE_COMPLETION = "phase_completion"

# Convergence
CONVERGED = True
NOT_CONVERGED = False

# Message types
MSG_TYPE_MESSAGE = "message"
MSG_TYPE_BROADCAST = "broadcast"
MSG_TYPE_SHUTDOWN_REQUEST = "shutdown_request"
MSG_TYPE_SHUTDOWN_RESPONSE = "shutdown_response"
MSG_TYPE_PLAN_APPROVAL = "plan_approval"

VALID_MSG_TYPES = {
    MSG_TYPE_MESSAGE,
    MSG_TYPE_BROADCAST,
    MSG_TYPE_SHUTDOWN_REQUEST,
    MSG_TYPE_SHUTDOWN_RESPONSE,
    MSG_TYPE_PLAN_APPROVAL,
}

# Tool names
TOOL_BASH = "bash"
TOOL_READ_FILE = "read_file"
TOOL_WRITE_FILE = "write_file"
TOOL_EDIT_FILE = "edit_file"
TOOL_TASK = "task"
TOOL_SPAWN = "spawn_teammate"
TOOL_LIST_TEAMMATES = "list_teammates"
TOOL_SEND_MESSAGE = "send_message"
TOOL_READ_INBOX = "read_inbox"
TOOL_BROADCAST = "broadcast"
TOOL_SHUTDOWN_REQUEST = "shutdown_request"
TOOL_SHUTDOWN_RESPONSE = "shutdown_response"
TOOL_PLAN_APPROVAL = "plan_approval"
TOOL_COMPACT = "compact"
TOOL_SAVE_STATE = "save_state"
TOOL_LOAD_STATE = "load_state"
TOOL_READ_DOC = "read_doc"
TOOL_WRITE_DOC = "write_doc"
TOOL_EDIT_DOC = "edit_doc"

# File names
SESSION_STATE_FILE = "session.json"
REQUIREMENTS_FILE = "requirements.md"
EXECUTION_PLAN_FILE = "execution-plan.md"
TECH_DESIGN_FILE = "tech-design.md"
ITERATION_SUMMARY_FILE = "iteration_summary.md"

# Prompt templates
ROLE_SYSTEM = {
    "orchestrator": "You are the orchestrator for an iterative document building system.",
    "builder_req": "You are a requirements analyst.",
    "builder_design": "You are a technical architect.",
    "reviewer_req": "You are a requirements review expert.",
    "reviewer_design": "You are a technical review expert.",
}
