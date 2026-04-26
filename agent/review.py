"""Multi-dimensional review analyzer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


@dataclass
class ReviewResult:
    """评审结果"""

    # 评审判断
    approved: bool  # 是否通过

    # 四维度评分
    scores: dict[str, int] = field(
        default_factory=dict
    )  # {"意图对齐": 5, "完整性": 4, ...}

    # 评审摘要
    summary: Optional[str] = None  # ≤ 500 字

    # 原始反馈
    raw_feedback: str = ""

    # 元信息
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ReviewAnalyzer:
    """多维度评审分析器"""

    # 维度名称映射（支持别名）
    DIMENSION_MAPPING = {
        "意图对齐": ["意图对齐", "意图一致性", "意图匹配", "意图"],
        "完整性": ["完整性", "完整度", "覆盖度", "覆盖性"],
        "可执行性": ["可执行性", "可执行", "可行性", "可实施性"],
        "格式合规": ["格式合规", "格式规范", "格式", "合规性"],
    }

    # 四维度名称（规范术语）
    DIMENSIONS = ["意图对齐", "完整性", "可执行性", "格式合规"]

    # 评分正则模式
    SCORE_PATTERN = re.compile(r"([\u4e00-\u9fa5a-zA-Z]{2,6})[：:]\s*(\d)")

    # 否定模式（优先级最高）
    NEGATIVE_PATTERNS = [
        r"not\s+.*\s+approved",  # not ... approved
        r"not\s+approved",  # not approved directly
        r"需修改",
        r"需要修改",
        r"修改后通过",
        r"需修改后通过",
        r"不通过",
        r"rejected",
        r"驳回",
        r"未通过",
        r"不行",
        r"有问题",
    ]

    # 通过模式
    APPROVED_PATTERNS = [
        r"评审(结果)?[：:]\s*通过",
        r"approved",
        r"审核通过",
        r"审查通过",
        r"pass",
        r"\bok\b",
        r"✓",
    ]

    def __init__(self) -> None:
        """初始化评审分析器"""
        self._negative_re = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATIVE_PATTERNS
        ]
        self._approved_re = [
            re.compile(p, re.IGNORECASE) for p in self.APPROVED_PATTERNS
        ]

    def analyze(
        self,
        raw_output: str,
        generate_summary: bool = True,
    ) -> ReviewResult:
        """
        分析原始评审输出

        Args:
            raw_output: LLM 原始评审输出
            generate_summary: 是否自动生成摘要（如果原始输出没有）

        Returns:
            ReviewResult 评审结果对象
        """
        result = ReviewResult(
            approved=self.check_approval(raw_output),
            raw_feedback=raw_output,
        )

        # 1. 提取四维度评分
        result.scores = self.extract_scores(raw_output)

        # 2. 提取或生成摘要
        if generate_summary:
            result.summary = self.extract_or_generate_summary(raw_output, result.scores)

        return result

    def extract_scores(self, output: str) -> dict[str, int]:
        """
        从评审输出提取四维度评分

        Args:
            output: 原始评审输出

        Returns:
            {"意图对齐": 5, "完整性": 4, ...}
        """
        scores: dict[str, int] = {}
        matches = self.SCORE_PATTERN.findall(output)

        for name, score_str in matches:
            score = int(score_str)

            # 验证范围
            if score < 1 or score > 5:
                continue

            # 映射到规范维度
            dimension = self._normalize_dimension(name)
            if dimension:
                scores[dimension] = score

        return scores

    def generate_summary(
        self,
        issues: list[str],
        max_length: int = 500,
    ) -> str:
        """
        基于问题列表生成评审摘要

        Args:
            issues: 问题列表
            max_length: 最大字符数

        Returns:
            摘要字符串（≤ max_length 字）
        """
        if not issues:
            return "文档整体良好，无明显问题。"

        # 合并问题
        summary_parts: list[str] = []
        current_length = 0

        for issue in issues:
            # 估算添加后的长度
            new_length = current_length + len(issue) + 2  # 2 for ", "

            if new_length > max_length:
                # 截断
                remaining = max_length - current_length - 4  # 4 for "..."
                if remaining > 10:
                    summary_parts.append(issue[:remaining] + "...")
                break

            summary_parts.append(issue)
            current_length = new_length

        if not summary_parts:
            return "文档存在一些问题，建议参考详细反馈。"

        summary = "主要问题：" + "；".join(summary_parts)

        # 最终截断
        if len(summary) > max_length:
            summary = summary[: max_length - 3] + "..."

        return summary

    def extract_or_generate_summary(
        self,
        output: str,
        scores: dict[str, int],
    ) -> str:
        """
        提取或生成评审摘要

        Args:
            output: 原始输出
            scores: 已提取的评分

        Returns:
            摘要字符串
        """
        # 1. 尝试提取已有摘要
        existing = self._extract_existing_summary(output)
        if existing and len(existing) <= 500:
            return existing

        # 2. 基于评分和问题生成摘要
        issues = self._extract_issues(output, scores)
        return self.generate_summary(issues)

    def check_approval(self, output: str) -> bool:
        """
        判断评审是否通过

        判断逻辑优先级：
        1. 否定模式优先（如"需修改"、"not approved"）
        2. 通过模式次之（如"通过"、"approved"）
        3. 默认：未通过

        Args:
            output: 原始评审输出

        Returns:
            True = 通过，False = 未通过
        """
        # 优先级1：检查否定模式
        for pattern in self._negative_re:
            if pattern.search(output):
                return False

        # 优先级2：检查通过模式
        for pattern in self._approved_re:
            if pattern.search(output):
                return True

        # 默认：未通过
        return False

    # === 私有方法 ===

    def _normalize_dimension(self, name: str) -> Optional[str]:
        """将维度名称标准化"""
        for standard, aliases in self.DIMENSION_MAPPING.items():
            if name in aliases:
                return standard
        return None

    def _extract_existing_summary(self, output: str) -> Optional[str]:
        """提取已有的摘要内容"""
        # 常见的摘要标记
        patterns = [
            r"摘要[：:]\s*([^\n]{0,500})",
            r"总结[：:]\s*([^\n]{0,500})",
            r"概述[：:]\s*([^\n]{0,500})",
            r"评审摘要[：:]\s*([^\n]{0,500})",
            r"主要反馈[：:]\s*([^\n]{0,500})",
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1).strip()

        return None

    def _extract_issues(
        self,
        output: str,
        scores: dict[str, int],
    ) -> list[str]:
        """从输出中提取问题列表"""
        issues: list[str] = []

        # 1. 基于低分维度
        for dim in self.DIMENSIONS:
            score = scores.get(dim, 3)  # 默认3分
            if score <= 2:
                issues.append(f"{dim}较低({score}分)")

        # 2. 提取"问题"、"建议"、"需要"等关键词后的内容
        problem_patterns = [
            r"问题[：:]\s*(.{10,100})",
            r"建议[：:]\s*(.{10,100})",
            r"需要[：:]\s*(.{10,100})",
            r"不足[：:]\s*(.{10,100})",
        ]

        for pattern in problem_patterns:
            matches = re.findall(pattern, output)
            issues.extend(matches[:3])  # 最多取3个

        return issues
