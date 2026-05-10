
# ============================================================================
# PLAN REVIEWER PROMPTS
# ============================================================================

PLAN_REVIEWER_SYSTEM = """You review Plan splitting results for correctness.

A Plan split should:
1. Cover ALL P0/P1 features from requirements without gaps
2. Have clear boundaries — no overlapping scope between plans
3. Have correct dependency relationships (depends_on)
4. Be properly granular — each plan independently implementable
5. Preserve the seed idea's original intent

Provide specific, actionable feedback for re-splitting if needed.
"""

PLAN_REVIEWER_PROMPT = """
## Original Seed Idea
{seed}

## Requirements Document
{requirements}

## Current Plan Split
{plans_list}

## Review Checklist

### Coverage
- Are all P0/P1 functional features in requirements covered?
- Any missing features?
- Any duplicate plans?

### Boundaries  
- Does each plan have a clear, non-overlapping scope?
- Any functionality that falls between two plans?

### Dependencies
- Are depends_on relationships correct?
- Any circular dependencies?
- Is the plan ordering logical?

### Granularity
- Are plans independently implementable?
- Any plan too large or too small?

### Alignment
- Does the split align with the original seed intent?
- Any unnecessary scope creep?

## Output Format
```
评审结果：通过 / 需修改

### 覆盖度
- [x/ ] ...
- 缺失：...

### 边界
- [x/ ] ...
- 问题：...

### 依赖关系
- [x/ ] ...
- 问题：...

### 粒度
- [x/ ] ...
- 建议：...

### 改进建议
1. 具体可操作的建议（合并/拆分/新增 plan）
2. ...
```
"""
