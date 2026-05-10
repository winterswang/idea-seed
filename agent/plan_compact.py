"""Plan-level context compression for v2.

Saves complete conversation transcripts for each Plan to disk
and keeps only plan_id, stage, status, summary in main context.

This allows independent iteration on each Plan without carrying
full conversation history in the main context.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.plan import Plan

_logger = logging.getLogger("idea-seed")


class PlanContextCompressor:
    """Handles context compression at the Plan level.

    Each Plan's full transcript is saved to:
        plans/{plan_id}/transcript/session_{timestamp}.jsonl

    The main context only retains:
        - plan_id
        - stage
        - status
        - summary (LLM-generated)
    """

    def __init__(self, project_dir: Path) -> None:
        """Initialize compressor for a project.

        Args:
            project_dir: Project root directory
        """
        self.project_dir = project_dir
        self.transcript_base = project_dir / "transcripts"
        self.plans_dir = project_dir / "plans"

    def compress_plan(
        self,
        plan_id: str,
        messages: list,
        summary: Optional[str] = None,
    ) -> dict:
        """Compress a Plan's conversation into summary + transcript.

        Args:
            plan_id: Plan identifier
            messages: Full conversation messages for this plan
            summary: Optional pre-generated summary

        Returns:
            Compressed info dict with plan_id, stage, status, summary
        """
        # Create transcript directory for this plan
        plan_transcript_dir = self.transcripts_dir_for(plan_id)
        plan_transcript_dir.mkdir(parents=True, exist_ok=True)

        # Save full transcript
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_file = plan_transcript_dir / f"session_{timestamp}.jsonl"

        with open(transcript_file, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        _logger.info(
            f"[PLAN_COMPACT] Saved transcript for {plan_id} to {transcript_file}"
        )

        # Generate summary if not provided
        if not summary:
            summary = self._generate_summary(messages)

        # Return compressed info (this is what goes into main context)
        return {
            "plan_id": plan_id,
            "transcript_path": str(transcript_file),
            "summary": summary,
            "message_count": len(messages),
        }

    def _generate_summary(self, messages: list) -> str:
        """Generate a summary of the plan's conversation.

        Args:
            messages: Conversation messages

        Returns:
            Summary string
        """
        # Simple extractive summary: collect key info from messages
        if not messages:
            return "No conversation yet."

        # Count tool uses and results
        tool_uses = sum(
            1 for m in messages
            if m.get("role") == "assistant" and isinstance(m.get("content"), list)
        )

        # Get last user message intent
        last_intent = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 10:
                    last_intent = content[:100]
                    break

        return (
            f"Plan conversation: {len(messages)} messages, "
            f"{tool_uses} tool uses. Last intent: {last_intent}"
        )

    def transcripts_dir_for(self, plan_id: str) -> Path:
        """Get transcript directory for a specific plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Path to transcript directory
        """
        return self.plans_dir / plan_id / "transcripts"

    def load_transcript(self, transcript_path: str) -> list:
        """Load a saved transcript.

        Args:
            transcript_path: Path to transcript file

        Returns:
            List of message dicts
        """
        path = Path(transcript_path)
        if not path.exists():
            _logger.warning(f"[PLAN_COMPACT] Transcript not found: {transcript_path}")
            return []

        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                messages.append(json.loads(line.strip()))
        return messages

    def list_transcripts(self, plan_id: str) -> list[Path]:
        """List all transcripts for a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            List of transcript file paths sorted by modification time
        """
        transcript_dir = self.transcripts_dir_for(plan_id)
        if not transcript_dir.exists():
            return []

        transcripts = sorted(
            transcript_dir.glob("session_*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return transcripts

    def get_latest_transcript(self, plan_id: str) -> Optional[list]:
        """Get the most recent transcript for a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            List of messages or None if no transcript exists
        """
        transcripts = self.list_transcripts(plan_id)
        if not transcripts:
            return None

        return self.load_transcript(str(transcripts[0]))

    def restore_from_transcript(self, transcript_path: str) -> list:
        """Restore conversation context from a saved transcript.

        Args:
            transcript_path: Path to transcript file

        Returns:
            Restored message list
        """
        return self.load_transcript(transcript_path)