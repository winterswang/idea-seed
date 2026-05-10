# Idea Seed Roadmap

> Last updated: 2026-05-10

## Completed (this session)

- [x] Code review: dead code, magic numbers, Logger split, hasattr cleanup
- [x] Builder prompt: scope discipline, first-line format, ban fabricated dates
- [x] Reviewer prompt: PASS RULE (suggestion-only → pass)
- [x] PlanSplitter: F-pattern matching (71→10 plans)
- [x] Issues #1 #2 #3 #4-3 #4-5 #4-6 #4-9 #4-10 resolved
- [x] 24 new unit tests (110 total)
- [x] E2E: seed → requirements → plans → tech-spec

### Direction C: Stability & Polish (COMPLETED)
- [x] C1: Tech-Spec token limit (80K→32K) + constants (a5b7692)
- [x] C2: `--style methodology|dev-doc` parameter #7 (a5b7692)
- [x] C3: Convergence "需求匹配度" dimension #9 (18c503e)

## Backlog: Direction A – Execution Reviewer

- [ ] Create `agent/execution_reviewer.py`
  - Read Tech-Spec → check file existence → verify interface → run tests → report
  - Auto-update Plan status via PlanManager
  - Dependency status propagation (upstream done → downstream unblocked)

## Backlog: Direction B – Incremental Append

- [ ] Replace heuristic keyword-match with LLM semantic fusion in handle_append
- [ ] Pre-append diff report + user confirmation
- [ ] Implement archive/ directory and supersede logic

## Backlog: Technical Debt

- [ ] #4-2 SessionState version compatibility (migration logic)
- [ ] #4-4 Auto-compact integration (orchestrator + subagent)
- [ ] #4-7 BUS/TEAM dependency injection for testability

## Backlog: Feature Requests

- [ ] #5 Full v2 Plan metadata as .md files (not just plans.json)
- [ ] #6 Multi-agent parallel Plan execution (team.py integration)
- [ ] #6 Execution phase state machine auto-advancement

## Known Issues

- [ ] Minimax model occasionally returns 0 output tokens (tech-spec phase, mitigated with 32K limit)
- [ ] PlanSplitter F-pattern only works for `#### F1:` format, no fallback for other heading styles
