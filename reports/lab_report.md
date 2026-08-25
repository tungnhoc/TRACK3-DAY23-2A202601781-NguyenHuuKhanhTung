# Day 23 Lab Report — LangGraph Support-Ticket Agent

## 1. Team / student

- Name: Nguyen Huu Khanh Tung
- Student ID: 2A202601781
- Repo/commit: https://github.com/tungnhoc/TRACK3-DAY23-2A202601781-NguyenHuuKhanhTung
- Date: 2026-08-25

## 2. Architecture

The system implements a multi-branch LangGraph stateful agent for customer support tickets with 11 specialized nodes:
- **intake**: Query normalization.
- **classify**: LLM-based intent routing with priority: risky > tool > missing_info > error > simple.
- **tool**: Tool execution with error simulation for transient failure testing.
- **evaluate**: Quality evaluation gate for retry loop.
- **answer**: LLM grounded response generation.
- **clarify**: Generates clarification questions for vague tickets or rejected approvals.
- **risky_action**: Prepares sensitive side-effect proposals for human review.
- **approval**: HITL approval gate.
- **retry**: Bounded attempt tracking and error recording.
- **dead_letter**: Fallback escalation for exhausted retries.
- **finalize**: Audit event logger before termination.

## 3. State schema

State schema design separates scalar state overwrites from append-only audit histories:

| Field | Reducer | Why |
|---|---|---|
| thread_id | overwrite | Identifies execution thread for checkpointer |
| scenario_id | overwrite | Audit metric tracking |
| query | overwrite | Normalized input query |
| route | overwrite | Classified intent (must NOT be overwritten at finalize) |
| risk_level | overwrite | Risk tier (high/low) |
| attempt | overwrite | Bounded retry loop counter |
| max_attempts | overwrite | Maximum retry limit |
| final_answer | overwrite | Final response text |
| evaluation_result | overwrite | Drives evaluate conditional routing |
| pending_question | overwrite | Stores clarification questions |
| proposed_action | overwrite | Stores pending risky actions |
| approval | overwrite | Human-in-the-loop approval decision |
| messages | append (`add`) | Preserves full message audit trail |
| tool_results | append (`add`) | Preserves full tool execution results |
| errors | append (`add`) | Preserves error logs across retries |
| events | append (`add`) | Comprehensive timeline for audit metrics |

## 4. Scenario results

**Overall Summary**:
- **Total Scenarios**: 7
- **Success Rate**: 100.0%
- **Average Nodes Visited**: 6.43
- **Total Retries**: 3
- **Total Interrupts/Approvals**: 2

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | ✅ True | 0 | 0 |
| S02_tool | tool | tool | ✅ True | 0 | 0 |
| S03_missing | missing_info | missing_info | ✅ True | 0 | 0 |
| S04_risky | risky | risky | ✅ True | 0 | 1 |
| S05_error | error | error | ✅ True | 2 | 0 |
| S06_delete | risky | risky | ✅ True | 0 | 1 |
| S07_dead_letter | error | error | ✅ True | 1 | 0 |

## 5. Failure analysis

1. **Transient Tool Failure & Bounded Retry Limit**:
   - *Scenario*: `S05_transient_error` & `S07_dead_letter`.
   - *Signal*: Tool returns `ERROR`. Node `evaluate` detects failure and routes to `retry`.
   - *Containment*: Counter `attempt` increments at `retry`. If `attempt < max_attempts`, re-enters `tool`. Once `attempt >= max_attempts`, routes to `dead_letter` to prevent infinite loops.
2. **Risky Action Rejected by Human Reviewer**:
   - *Scenario*: `S06_risky_rejected`.
   - *Signal*: Human reviewer sets `approved=False` at the `approval` gate.
   - *Containment*: `route_after_approval` inspects `approval` and routes directly to `clarify`, bypassing the `tool` node entirely to prevent unauthorized side-effects.

## 6. Persistence / recovery evidence

The graph is compiled with a Checkpointer (`MemorySaver` or `SqliteSaver`). Each scenario execution passes a unique `thread_id` via configuration: `{'configurable': {'thread_id': state['thread_id']}}`. State history and audit event trails are preserved per thread, enabling state inspection, crash-resume, and audit reporting.

## 7. Extension work

- Integrated `python-dotenv` for dynamic environment configuration.
- Implemented LLM structured output via Pydantic (`ClassificationOutput`) for intent routing with Gemini `gemini-3.6-flash`.
- Built automated CLI metric runner and Pydantic validator.

## 8. Improvement plan

If allocated another day, the top production priority would be implementing full LLM-as-judge evaluation in `evaluate_node` to validate complex tool responses against semantic criteria, along with persistent SQLite checkpointer storage for production restart resiliency.
