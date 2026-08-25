"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data."""
    lines = []
    lines.append("# Day 23 Lab Report — LangGraph Support-Ticket Agent")
    lines.append("")
    lines.append("## 1. Team / student")
    lines.append("")
    lines.append("- Name: Nguyen Huu Khanh Tung")
    lines.append("- Student ID: 2A202601781")
    lines.append("- Repo/commit: https://github.com/tungnhoc/TRACK3-DAY23-2A202601781-NguyenHuuKhanhTung")
    lines.append("- Date: 2026-08-25")
    lines.append("")
    lines.append("## 2. Architecture")
    lines.append("")
    lines.append(
        "The system implements a multi-branch LangGraph stateful agent for customer support tickets with 11 specialized nodes:\n"
        "- **intake**: Query normalization.\n"
        "- **classify**: LLM-based intent routing with priority: risky > tool > missing_info > error > simple.\n"
        "- **tool**: Tool execution with error simulation for transient failure testing.\n"
        "- **evaluate**: Quality evaluation gate for retry loop.\n"
        "- **answer**: LLM grounded response generation.\n"
        "- **clarify**: Generates clarification questions for vague tickets or rejected approvals.\n"
        "- **risky_action**: Prepares sensitive side-effect proposals for human review.\n"
        "- **approval**: HITL approval gate.\n"
        "- **retry**: Bounded attempt tracking and error recording.\n"
        "- **dead_letter**: Fallback escalation for exhausted retries.\n"
        "- **finalize**: Audit event logger before termination."
    )
    lines.append("")
    lines.append("## 3. State schema")
    lines.append("")
    lines.append("State schema design separates scalar state overwrites from append-only audit histories:")
    lines.append("")
    lines.append("| Field | Reducer | Why |")
    lines.append("|---|---|---|")
    lines.append("| thread_id | overwrite | Identifies execution thread for checkpointer |")
    lines.append("| scenario_id | overwrite | Audit metric tracking |")
    lines.append("| query | overwrite | Normalized input query |")
    lines.append("| route | overwrite | Classified intent (must NOT be overwritten at finalize) |")
    lines.append("| risk_level | overwrite | Risk tier (high/low) |")
    lines.append("| attempt | overwrite | Bounded retry loop counter |")
    lines.append("| max_attempts | overwrite | Maximum retry limit |")
    lines.append("| final_answer | overwrite | Final response text |")
    lines.append("| evaluation_result | overwrite | Drives evaluate conditional routing |")
    lines.append("| pending_question | overwrite | Stores clarification questions |")
    lines.append("| proposed_action | overwrite | Stores pending risky actions |")
    lines.append("| approval | overwrite | Human-in-the-loop approval decision |")
    lines.append("| messages | append (`add`) | Preserves full message audit trail |")
    lines.append("| tool_results | append (`add`) | Preserves full tool execution results |")
    lines.append("| errors | append (`add`) | Preserves error logs across retries |")
    lines.append("| events | append (`add`) | Comprehensive timeline for audit metrics |")
    lines.append("")
    lines.append("## 4. Scenario results")
    lines.append("")
    lines.append("**Overall Summary**:")
    lines.append(f"- **Total Scenarios**: {metrics.total_scenarios}")
    lines.append(f"- **Success Rate**: {metrics.success_rate * 100:.1f}%")
    lines.append(f"- **Average Nodes Visited**: {metrics.avg_nodes_visited:.2f}")
    lines.append(f"- **Total Retries**: {metrics.total_retries}")
    lines.append(f"- **Total Interrupts/Approvals**: {metrics.total_interrupts}")
    lines.append("")
    lines.append("| Scenario | Expected route | Actual route | Success | Retries | Interrupts |")
    lines.append("|---|---|---|---:|---:|---:|")
    for sm in metrics.scenario_metrics:
        lines.append(
            f"| {sm.scenario_id} | {sm.expected_route} | {sm.actual_route or 'N/A'} | "
            f"{'✅ True' if sm.success else '❌ False'} | {sm.retry_count} | {sm.interrupt_count} |"
        )
    lines.append("")
    lines.append("## 5. Failure analysis")
    lines.append("")
    lines.append("1. **Transient Tool Failure & Bounded Retry Limit**:")
    lines.append(
        "   - *Scenario*: `S05_transient_error` & `S07_dead_letter`.\n"
        "   - *Signal*: Tool returns `ERROR`. Node `evaluate` detects failure and routes to `retry`.\n"
        "   - *Containment*: Counter `attempt` increments at `retry`. If `attempt < max_attempts`, re-enters `tool`. Once `attempt >= max_attempts`, routes to `dead_letter` to prevent infinite loops."
    )
    lines.append("2. **Risky Action Rejected by Human Reviewer**:")
    lines.append(
        "   - *Scenario*: `S06_risky_rejected`.\n"
        "   - *Signal*: Human reviewer sets `approved=False` at the `approval` gate.\n"
        "   - *Containment*: `route_after_approval` inspects `approval` and routes directly to `clarify`, bypassing the `tool` node entirely to prevent unauthorized side-effects."
    )
    lines.append("")
    lines.append("## 6. Persistence / recovery evidence")
    lines.append("")
    lines.append(
        "The graph is compiled with a Checkpointer (`MemorySaver` or `SqliteSaver`). Each scenario execution passes a unique `thread_id` via configuration: `{'configurable': {'thread_id': state['thread_id']}}`. State history and audit event trails are preserved per thread, enabling state inspection, crash-resume, and audit reporting."
    )
    lines.append("")
    lines.append("## 7. Extension work")
    lines.append("")
    lines.append(
        "- Integrated `python-dotenv` for dynamic environment configuration.\n"
        "- Implemented LLM structured output via Pydantic (`ClassificationOutput`) for intent routing with Gemini `gemini-3.6-flash`.\n"
        "- Built automated CLI metric runner and Pydantic validator."
    )
    lines.append("")
    lines.append("## 8. Improvement plan")
    lines.append("")
    lines.append(
        "If allocated another day, the top production priority would be implementing full LLM-as-judge evaluation in `evaluate_node` to validate complex tool responses against semantic criteria, along with persistent SQLite checkpointer storage for production restart resiliency."
    )
    lines.append("")
    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
