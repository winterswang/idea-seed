"""Orchestrator - main workflow controller with logging and project directories."""

import hashlib
import re
import time
import uuid
from pathlib import Path
from datetime import datetime

from agent.config import WORKDIR
from agent.state import SessionState, save_state, load_state
from agent.constants import (
    PHASE_REQUIREMENTS,
    PHASE_TECH_DESIGN,
    PHASE_DONE,
    REQUIREMENTS_FILE,
    TECH_DESIGN_FILE,
    ITERATION_SUMMARY_FILE,
)
from agent.subagent import run_subagent
from agent.prompts import (
    BUILDER_REQ_SYSTEM,
    BUILDER_REQ_PROMPT,
    BUILDER_DESIGN_SYSTEM,
    BUILDER_DESIGN_PROMPT,
    REVIEWER_REQ_SYSTEM,
    REVIEWER_REQ_PROMPT,
    REVIEWER_DESIGN_SYSTEM,
    REVIEWER_DESIGN_PROMPT,
)


def slugify(text: str) -> str:
    """
    Convert seed text to a short, readable project directory name.

    Format: {keyword1}-{keyword2}-{keyword3}-{hash4}
    Example: 财务工具-接口封装-akshare-7f2a

    Args:
        text: The seed idea text

    Returns:
        Short directory-friendly name
    """
    # Extract Chinese words (2-4 characters)
    chinese_words = re.findall(r"[\u4e00-\u9fff]{2,4}", text)

    # Extract English words/phrases
    english_words = re.findall(r"[a-zA-Z]{2,10}", text.lower())

    # Filter out common stop words for both
    cn_stop = {
        "的",
        "是",
        "在",
        "和",
        "了",
        "我",
        "你",
        "他",
        "她",
        "它",
        "们",
        "这",
        "那",
        "有",
        "个",
        "们",
        "与",
        "及",
        "或",
        "等",
        "要",
        "会",
        "对",
        "把",
        "被",
        "从",
        "到",
        "给",
        "用",
        "为",
        "以",
        "及",
        "上",
        "下",
        "中",
        "内",
        "外",
        "后",
        "前",
        "里",
        "还",
        "也",
        "很",
        "都",
    }

    en_stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "these",
        "those",
        "are",
        "was",
        "were",
        "been",
        "have",
        "has",
        "had",
        "but",
        "not",
        "you",
        "your",
        "can",
        "will",
        "all",
        "one",
        "two",
    }

    chinese_words = [w for w in chinese_words if w not in cn_stop]
    english_words = [w for w in english_words if w not in en_stop and len(w) > 2]

    # Combine and prioritize: English first, then Chinese
    keywords = english_words[:2] + chinese_words[:3]

    # If no keywords found, fallback to simple truncation
    if not keywords:
        slug = re.sub(r"[^\w\u4e00-\u9fff-]", "", text)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:20]

    # Take top 3-4 keywords
    keywords = keywords[:4]

    # Calculate 4-char hash from lowercase text for uniqueness (case-insensitive)
    hash_suffix = hashlib.md5(text.lower().encode()).hexdigest()[:4]

    return "-".join(keywords) + "-" + hash_suffix


def check_approval(review_result: str) -> bool:
    """
    Check if a review result indicates approval.

    Uses a priority-based approach:
    1. Negation patterns (not ... approved) are checked first
    2. Rejection indicators (需修改, rejected, etc.) are checked next
    3. Approval indicators are checked last

    Args:
        review_result: The text output from the reviewer

    Returns:
        True if approved, False otherwise
    """
    result_lower = review_result.lower()

    # Priority 1: Check for negation patterns that override approval
    # These always result in rejection
    negation_patterns = [
        "not ",  # English negation prefix (not approved, not fully approved, etc.)
        "需修改",  # Chinese: needs modification
        "rejected",  # English: rejected
    ]
    for pattern in negation_patterns:
        if pattern.lower() in result_lower:
            # Special case: "not" needs to be followed by "approved"
            if pattern == "not ":
                if "approved" in result_lower:
                    return False  # "not ... approved" is rejection
                # "not" without "approved" - ignore, might be "not needed" etc.
                continue
            return False

    # Priority 2: Check for approval indicators
    approval_patterns = [
        "评审结果",  # Has explicit verdict line
        "approved",  # English approval (not negated)
        "通过",  # Chinese approval (anywhere)
    ]
    for pattern in approval_patterns:
        if pattern.lower() in result_lower:
            return True

    # Default: not approved
    return False


class Logger:
    """Simple file logger for tracking execution."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: str = "INFO") -> None:
        """Write log entry with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}\n"
        with open(self.log_path, "a") as f:
            f.write(entry)
        print(entry.rstrip())

    def log_section(self, title: str) -> None:
        """Log a section header."""
        separator = "=" * 60
        self.log(separator)
        self.log(title)
        self.log(separator)


class Orchestrator:
    """Main orchestrator for iterative document building."""

    def __init__(
        self,
        seed: str,
        resume: bool = False,
        max_rounds: int | None = None,
    ) -> None:
        """
        Initialize orchestrator.

        Args:
            seed: The original seed idea
            resume: Whether to resume from saved state
            max_rounds: Maximum rounds per phase (default: 10)
        """
        from agent.config import MAX_ROUNDS

        self.max_rounds = max_rounds if max_rounds is not None else MAX_ROUNDS
        # Create project directory based on seed
        self.project_slug = slugify(seed)
        self.project_dir = WORKDIR / "projects" / self.project_slug
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Set up logger
        self.log_path = self.project_dir / "execution.log"
        self.logger = Logger(self.log_path)

        # Initialize directories
        self.state_dir = self.project_dir / ".state"
        self.state_dir.mkdir(exist_ok=True)

        # Create rounds subdirectories for versioned artifacts
        self.rounds_dir = self.project_dir / "rounds"
        self.req_rounds_dir = self.rounds_dir / "requirements"
        self.design_rounds_dir = self.rounds_dir / "designs"
        self.review_rounds_dir = self.rounds_dir / "reviews"
        self.req_rounds_dir.mkdir(parents=True, exist_ok=True)
        self.design_rounds_dir.mkdir(parents=True, exist_ok=True)
        self.review_rounds_dir.mkdir(parents=True, exist_ok=True)

        # Resume or create new
        state_file = self.state_dir / "session.json"
        if resume and state_file.exists():
            self.state = load_state(state_file)
            self.logger.log(f"Resumed session: {self.state.session_id}")
        else:
            self.state = SessionState(
                session_id=str(uuid.uuid4()),
                seed=seed,
                phase=PHASE_REQUIREMENTS,
            )
            save_state(self.state, state_file)
            self.logger.log(f"Started new session: {self.state.session_id}")

        self.logger.log("")
        self.logger.log(f"{'=' * 60}")
        self.logger.log("  IDEA SEED - Iterative Document Builder")
        self.logger.log(f"{'=' * 60}")
        self.logger.log(f"  🌱 Seed: {self.state.seed}")
        self.logger.log(f"  📁 Project: {self.project_dir}")
        self.logger.log(f"  📋 Session: {self.state.session_id}")
        self.logger.log(f"  📍 Phase: {self.state.phase.upper()}")
        self.logger.log(f"  🔄 Max Rounds: {self.max_rounds}")
        self.logger.log("  🎯 Convergence: 2 consecutive approvals needed")
        self.logger.log(f"{'=' * 60}")
        self.logger.log("")

    @property
    def requirements_path(self) -> Path:
        return self.project_dir / REQUIREMENTS_FILE

    @property
    def tech_design_path(self) -> Path:
        return self.project_dir / TECH_DESIGN_FILE

    @property
    def summary_path(self) -> Path:
        return self.project_dir / ITERATION_SUMMARY_FILE

    def run(self) -> None:
        """Main execution loop."""
        start_time = time.time()

        try:
            while not self.state.is_done():
                if self.state.phase == PHASE_REQUIREMENTS:
                    self._run_requirements_phase()
                elif self.state.phase == PHASE_TECH_DESIGN:
                    self._run_design_phase()
                elif self.state.phase == PHASE_DONE:
                    self._output_final_docs()
                    break

                self._save_state()

        except KeyboardInterrupt:
            self.logger.log("Interrupted by user", "WARN")
            self._save_state()
            raise

        elapsed = time.time() - start_time
        self.logger.log(f"Total execution time: {elapsed:.1f} seconds")

    def _run_requirements_phase(self) -> None:
        """Run one round of requirements building."""
        self.state.req_round += 1

        # Calculate progress toward convergence
        review_count = len(self.state.req_review_history)
        recent_approved = (
            sum(1 for r in self.state.req_review_history[-2:])
            if review_count >= 1
            else 0
        )
        progress = f"[Round {self.state.req_round}/{self.max_rounds}] [Recent approvals: {recent_approved}/2]"

        self.logger.log("")
        self.logger.log(f"{'=' * 60}")
        self.logger.log(f"  REQUIREMENTS PHASE - Round {self.state.req_round}")
        self.logger.log(f"  Progress: {progress}")
        self.logger.log(f"{'=' * 60}")

        if self.state.req_round > self.max_rounds:
            self.logger.log("Max rounds reached, forcing convergence", "WARN")
            self.state.req_converged = True
            self.state.phase = PHASE_TECH_DESIGN
            return

        # Get previous feedback
        feedback = None
        if self.state.req_review_history:
            last_review = self.state.req_review_history[-1]
            feedback = last_review.get("feedback")

        # File path for this round's requirements
        round_req_path = self.req_rounds_dir / f"round-{self.state.req_round}.md"

        # Run Builder - subagent writes directly to file
        self.logger.log("")
        self.logger.log("  [1/2] Running Requirements Builder...")
        start_time = time.time()
        self._builder_req_build(feedback, str(round_req_path))
        build_time = time.time() - start_time

        # Read back the file content that subagent wrote
        requirements = self._read_doc(round_req_path)
        req_lines = requirements.count("\n")
        self.logger.log(
            f"      → Generated {req_lines} lines, {len(requirements)} chars in {build_time:.1f}s"
        )
        self.logger.log(
            f"      → Written to: rounds/requirements/round-{self.state.req_round}.md"
        )

        # Also update latest copy
        self._write_doc(self.requirements_path, requirements)
        self.logger.log("      → Updated: requirements.md (latest)")

        # Run Reviewer
        self.logger.log("")
        self.logger.log("  [2/2] Running Requirements Reviewer...")
        review_result = self._reviewer_req_review(requirements)
        self.state.req_review_history.append(review_result)

        approved = "✅ APPROVED" if review_result["approved"] else "❌ NEEDS WORK"
        self.logger.log(f"      → Review: {approved}")

        # Save round-specific review report
        round_review_path = (
            self.review_rounds_dir / f"requirements-round-{self.state.req_round}.md"
        )
        review_content = self._format_review_report(
            phase="Requirements",
            round_num=self.state.req_round,
            seed=self.state.seed,
            approved=review_result["approved"],
            feedback=review_result["feedback"],
            document=requirements,
        )
        self._write_doc(round_review_path, review_content)
        self.logger.log(
            f"      → Review saved to: rounds/reviews/requirements-round-{self.state.req_round}.md"
        )

        if review_result["feedback"]:
            fb_preview = review_result["feedback"][:300].replace("\n", " ")
            self.logger.log(f"      → Feedback: {fb_preview}...")

        # Check convergence
        if self._check_req_convergence():
            self.logger.log("")
            self.logger.log("  🎉 CONVERGENCE REACHED! Requirements are stable.")
            self.state.req_converged = True
            self.state.phase = PHASE_TECH_DESIGN
        else:
            self.logger.log("")
            self.logger.log(
                f"  → Not converged yet. ({recent_approved + (1 if review_result['approved'] else 0)}/2 recent approvals needed)"
            )

    def _run_design_phase(self) -> None:
        """Run one round of technical design building."""
        self.state.design_round += 1

        # Calculate progress toward convergence
        review_count = len(self.state.design_review_history)
        recent_approved = (
            sum(1 for r in self.state.design_review_history[-2:])
            if review_count >= 1
            else 0
        )
        progress = f"[Round {self.state.design_round}/{self.max_rounds}] [Recent approvals: {recent_approved}/2]"

        self.logger.log("")
        self.logger.log(f"{'=' * 60}")
        self.logger.log(f"  TECH DESIGN PHASE - Round {self.state.design_round}")
        self.logger.log(f"  Progress: {progress}")
        self.logger.log(f"{'=' * 60}")

        if self.state.design_round > self.max_rounds:
            self.logger.log("Max rounds reached, forcing convergence", "WARN")
            self.state.design_converged = True
            self.state.phase = PHASE_DONE
            return

        # Get previous feedback
        feedback = None
        if self.state.design_review_history:
            last_review = self.state.design_review_history[-1]
            feedback = last_review.get("feedback")

        # Read requirements
        self.logger.log("")
        self.logger.log("  [1/3] Reading requirements...")
        requirements = self._read_doc(self.requirements_path)
        req_lines = requirements.count("\n")
        self.logger.log(f"      → Loaded {req_lines} lines from requirements.md")

        # File path for this round's design
        round_design_path = (
            self.design_rounds_dir / f"round-{self.state.design_round}.md"
        )

        # Run Builder - subagent writes directly to file
        self.logger.log("  [2/3] Running Design Builder...")
        start_time = time.time()
        self._builder_design_build(requirements, feedback, str(round_design_path))
        build_time = time.time() - start_time

        # Read back the file content that subagent wrote
        tech_design = self._read_doc(round_design_path)
        design_lines = tech_design.count("\n")
        self.logger.log(
            f"      → Generated {design_lines} lines, {len(tech_design)} chars in {build_time:.1f}s"
        )
        self.logger.log(
            f"      → Written to: rounds/designs/round-{self.state.design_round}.md"
        )

        # Also update latest copy
        self._write_doc(self.tech_design_path, tech_design)
        self.logger.log("      → Updated: tech-design.md (latest)")

        # Run Reviewer
        self.logger.log("  [3/3] Running Design Reviewer...")
        review_result = self._reviewer_design_review(requirements, tech_design)
        self.state.design_review_history.append(review_result)

        approved = "✅ APPROVED" if review_result["approved"] else "❌ NEEDS WORK"
        self.logger.log(f"      → Review: {approved}")

        # Save round-specific review report
        round_review_path = (
            self.review_rounds_dir / f"design-round-{self.state.design_round}.md"
        )
        review_content = self._format_review_report(
            phase="Tech Design",
            round_num=self.state.design_round,
            seed=self.state.seed,
            approved=review_result["approved"],
            feedback=review_result["feedback"],
            document=tech_design,
        )
        self._write_doc(round_review_path, review_content)
        self.logger.log(
            f"      → Review saved to: rounds/reviews/design-round-{self.state.design_round}.md"
        )

        if review_result["feedback"]:
            fb_preview = review_result["feedback"][:300].replace("\n", " ")
            self.logger.log(f"      → Feedback: {fb_preview}...")

        # Check convergence
        if self._check_design_convergence():
            self.logger.log("")
            self.logger.log("  🎉 CONVERGENCE REACHED! Tech design is stable.")
            self.state.design_converged = True
            self.state.phase = PHASE_DONE
        else:
            self.logger.log("")
            self.logger.log(
                f"  → Not converged yet. ({recent_approved + (1 if review_result['approved'] else 0)}/2 recent approvals needed)"
            )

    def _check_req_convergence(self) -> bool:
        """Check if requirements phase has converged."""
        if len(self.state.req_review_history) < 2:
            return False
        last_two = self.state.req_review_history[-2:]
        return all(r.get("approved", False) for r in last_two)

    def _check_design_convergence(self) -> bool:
        """Check if design phase has converged."""
        if len(self.state.design_review_history) < 2:
            return False
        last_two = self.state.design_review_history[-2:]
        return all(r.get("approved", False) for r in last_two)

    def _builder_req_build(self, feedback: str | None, req_path: str) -> None:
        """Run requirements builder - writes directly to file."""
        # Feedback is already just the previous round's feedback (not cumulative)
        # passed in from _run_requirements_phase
        prompt = BUILDER_REQ_PROMPT.format(
            seed=self.state.seed,
            previous_feedback=feedback or "None - first iteration",
            req_path=req_path,
        )

        # Subagent writes directly to file, returns confirmation message
        run_subagent(prompt=prompt, system=BUILDER_REQ_SYSTEM)

    def _builder_design_build(
        self, requirements: str, feedback: str | None, design_path: str
    ) -> None:
        """Run technical design builder - writes directly to file."""
        # Feedback is already just the previous round's feedback (not cumulative)
        # passed in from _run_design_phase
        prompt = BUILDER_DESIGN_PROMPT.format(
            requirements=requirements,
            previous_feedback=feedback or "None - first iteration",
            design_path=design_path,
        )

        # Subagent writes directly to file, returns confirmation message
        run_subagent(prompt=prompt, system=BUILDER_DESIGN_SYSTEM)

    def _reviewer_req_review(self, requirements: str) -> dict:
        """Run requirements reviewer."""
        prompt = REVIEWER_REQ_PROMPT.format(
            seed=self.state.seed,
            requirements=requirements,
        )

        result = run_subagent(prompt=prompt, system=REVIEWER_REQ_SYSTEM)

        # Parse result to determine if approved
        approved = check_approval(result)
        feedback = result if not approved else None

        return {
            "approved": approved,
            "feedback": feedback,
            "round": self.state.req_round,
        }

    def _reviewer_design_review(self, requirements: str, tech_design: str) -> dict:
        """Run technical design reviewer."""
        prompt = REVIEWER_DESIGN_PROMPT.format(
            seed=self.state.seed,
            requirements=requirements,
            tech_design=tech_design,
        )

        result = run_subagent(prompt=prompt, system=REVIEWER_DESIGN_SYSTEM)

        # Parse result to determine if approved
        approved = check_approval(result)
        feedback = result if not approved else None

        return {
            "approved": approved,
            "feedback": feedback,
            "round": self.state.design_round,
        }

    def _read_doc(self, path: Path) -> str:
        """Read document from path."""
        if path.exists():
            return path.read_text()
        return ""

    def _write_doc(self, path: Path, content: str) -> None:
        """Write document to path with validation."""
        # Ensure path is within project directory
        try:
            path.resolve().relative_to(self.project_dir.resolve())
        except ValueError:
            raise ValueError(
                f"Path {path} escapes project directory {self.project_dir}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _save_state(self) -> None:
        """Save session state."""
        save_state(self.state, self.state_dir / "session.json")

    def _output_final_docs(self) -> None:
        """Output final documents summary."""
        self.logger.log("")
        self.logger.log(f"{'=' * 60}")
        self.logger.log("  DOCUMENT BUILDING COMPLETE")
        self.logger.log(f"{'=' * 60}")
        self.logger.log(f"  Seed Idea: {self.state.seed}")
        self.logger.log(f"  Requirements Rounds: {self.state.req_round}")
        self.logger.log(f"  Design Rounds: {self.state.design_round}")

        # Show convergence status
        self.logger.log("")
        self.logger.log("  Convergence Status:")
        self.logger.log(
            f"    Requirements: {'✅ Converged' if self.state.req_converged else '⚠️ Forced (max rounds)'}"
        )
        self.logger.log(
            f"    Tech Design:  {'✅ Converged' if self.state.design_converged else '⚠️ Forced (max rounds)'}"
        )

        # Show review history summary
        if self.state.req_review_history:
            self.logger.log("")
            self.logger.log("  Requirements Review History:")
            for r in self.state.req_review_history:
                status = "✅" if r["approved"] else "❌"
                self.logger.log(f"    Round {r['round']}: {status}")

        if self.state.design_review_history:
            self.logger.log("")
            self.logger.log("  Tech Design Review History:")
            for r in self.state.design_review_history:
                status = "✅" if r["approved"] else "❌"
                self.logger.log(f"    Round {r['round']}: {status}")

        self.logger.log("")
        self.logger.log("  Output Files:")
        self.logger.log(f"    📄 {self.requirements_path} (latest)")
        self.logger.log(f"    📄 {self.tech_design_path} (latest)")
        self.logger.log(f"    📝 {self.log_path}")

        # Show rounds directory structure
        self.logger.log("")
        self.logger.log("  Versioned Rounds:")
        self.logger.log(f"    📁 {self.rounds_dir}/")
        self.logger.log(f"       ├── requirements/ ({self.state.req_round} rounds)")
        self.logger.log(f"       ├── designs/ ({self.state.design_round} rounds)")
        self.logger.log("       └── reviews/ (all review reports)")

        # Generate iteration summary
        summary = self._generate_summary()
        self._write_doc(self.summary_path, summary)
        self.logger.log(f"    📋 {self.summary_path}")

        self.logger.log("")
        self.logger.log(f"{'=' * 60}")
        self.logger.log("  COMPLETE")
        self.logger.log(f"{'=' * 60}")

    def _format_review_report(
        self,
        phase: str,
        round_num: int,
        seed: str,
        approved: bool,
        feedback: str | None,
        document: str,
    ) -> str:
        """Format a round review report with document content."""
        timestamp = datetime.now().isoformat()
        status = "✅ APPROVED" if approved else "❌ NEEDS WORK"

        lines = [
            f"# {phase} 评审报告 - Round {round_num}",
            "",
            "## 元信息",
            f"- **种子想法**: {seed}",
            f"- **评审轮次**: Round {round_num}",
            f"- **评审时间**: {timestamp}",
            f"- **评审结果**: {status}",
            "",
            "## 评审反馈",
            "",
        ]

        if feedback:
            lines.append(feedback)
        else:
            lines.append("_（无反馈 - 文档已通过评审）_")

        lines.extend(
            [
                "",
                "## 评审文档内容",
                "",
                "---",
                document,
                "---",
            ]
        )

        return "\n".join(lines)

    def _generate_summary(self) -> str:
        """Generate iteration summary markdown."""
        lines = [
            "# 迭代总结",
            "",
            "## 会话信息",
            f"- **种子想法**: {self.state.seed}",
            f"- **会话ID**: {self.state.session_id}",
            f"- **开始时间**: {self.state.created_at}",
            f"- **结束时间**: {datetime.now().isoformat()}",
            "",
            "## 需求阶段",
            f"- **迭代轮次**: {self.state.req_round} 轮",
            f"- **收敛原因**: {'通过' if self.state.req_converged and self.state.req_round <= 10 else '达到上限'}",
            "",
            "## 方案阶段",
            f"- **迭代轮次**: {self.state.design_round} 轮",
            f"- **收敛原因**: {'通过' if self.state.design_converged and self.state.design_round <= 10 else '达到上限'}",
            "",
            "## 评审历史",
            "",
        ]

        if self.state.req_review_history:
            lines.append("### 需求评审")
            for r in self.state.req_review_history:
                status = "✅" if r["approved"] else "❌"
                lines.append(
                    f"- Round {r['round']}: {status} → `rounds/reviews/requirements-round-{r['round']}.md`"
                )
            lines.append("")

        if self.state.design_review_history:
            lines.append("### 方案评审")
            for r in self.state.design_review_history:
                status = "✅" if r["approved"] else "❌"
                lines.append(
                    f"- Round {r['round']}: {status} → `rounds/reviews/design-round-{r['round']}.md`"
                )
            lines.append("")

        lines.extend(
            [
                "## 产出文档结构",
                "",
                "```",
                f"projects/{self.project_slug}/",
                "├── rounds/",
                "│   ├── requirements/",
            ]
        )

        for i in range(1, self.state.req_round + 1):
            lines.append(f"│   │   └── round-{i}.md")

        lines.extend(
            [
                "│   ├── designs/",
            ]
        )

        for i in range(1, self.state.design_round + 1):
            lines.append(f"│   │   └── round-{i}.md")

        lines.extend(
            [
                "│   └── reviews/",
                "│       ├── requirements-round-1.md",
                "│       └── design-round-1.md",
                "├── requirements.md  (latest)",
                "├── tech-design.md   (latest)",
                "├── session.json",
                "├── execution.log",
                "└── iteration_summary.md",
                "```",
            ]
        )

        return "\n".join(lines)
