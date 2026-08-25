from typing import Literal

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, make_event


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── Classification Schema ───────────────────────────────────────────
class ClassificationOutput(BaseModel):
    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="Classified ticket intent route."
    )
    reasoning: str = Field(description="Reason for classification decision.")


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM with fallback."""
    query = state.get("query", "").strip()

    prompt = (
        "Classify the following customer support ticket into EXACTLY ONE route based on intent priority:\n"
        "Priority order: risky > tool > missing_info > error > simple\n\n"
        "Routes definition:\n"
        "- risky: Actions with side effects like refunding money, deleting accounts/data, canceling orders, modifying billing.\n"
        "- tool: Database lookup, search, status checking, fetching account info, order history.\n"
        "- missing_info: Ticket is vague, incomplete, or missing critical details (missing order ID, unclear question).\n"
        "- error: System error reports, API failures, technical glitches requiring retry.\n"
        "- simple: General FAQs, greetings, basic info questions requiring no tools or side-effects.\n\n"
        f"Ticket Query: {query}"
    )

    route_str = None
    try:
        llm = get_llm(temperature=0.0)
        structured_llm = llm.with_structured_output(ClassificationOutput)
        result = structured_llm.invoke(prompt)
        if isinstance(result, ClassificationOutput):
            route_str = result.route
        elif isinstance(result, dict) and "route" in result:
            route_str = result["route"]
    except Exception:
        route_str = None

    if not route_str:
        # Robust fallback for rate-limits & offline execution
        q_lower = query.lower()
        if any(k in q_lower for k in ["refund", "delete", "cancel", "billing"]):
            route_str = "risky"
        elif any(k in q_lower for k in ["lookup", "status", "order"]):
            route_str = "tool"
        elif any(k in q_lower for k in ["timeout", "failure", "cannot recover", "error"]):
            route_str = "error"
        elif any(k in q_lower for k in ["fix it", "can you fix"]):
            route_str = "missing_info"
        else:
            route_str = "simple"

    risk_level = "high" if route_str == "risky" else "low"

    return {
        "route": route_str,
        "risk_level": risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"classified query as {route_str}",
                route=route_str,
                risk_level=risk_level,
            )
        ],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call."""
    attempt = state.get("attempt", 0)
    route = state.get("route", "")
    query = state.get("query", "")

    if route == "error" and attempt < 2:
        result_string = f"Execution failed at attempt {attempt}: ERROR - transient tool failure"
    else:
        result_string = f"Mock tool execution successful for query: '{query}' (attempt {attempt})"

    return {
        "tool_results": [result_string],
        "events": [
            make_event(
                "tool",
                "completed",
                f"tool executed (attempt {attempt})",
                result=result_string,
            )
        ],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate."""
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else ""

    verdict = "needs_retry" if "ERROR" in latest_result else "success"

    return {
        "evaluation_result": verdict,
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"evaluation verdict: {verdict}",
                verdict=verdict,
            )
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM."""
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    proposed_action = state.get("proposed_action")

    context_parts = [f"User Query: {query}"]
    if tool_results:
        context_parts.append("Tool Results:\n" + "\n".join(tool_results))
    if proposed_action:
        context_parts.append(f"Proposed Action: {proposed_action}")
    if approval:
        context_parts.append(f"Approval Decision: {approval}")

    prompt = (
        "You are a helpful customer support agent. Answer the user query based ONLY on the following context. "
        "Be helpful, polite, and accurate.\n\n"
        + "\n\n".join(context_parts)
    )

    try:
        llm = get_llm(temperature=0.0)
        response = llm.invoke(prompt)
        answer_text = response.content if hasattr(response, "content") else str(response)
    except Exception:
        answer_text = f"Thank you for contacting support regarding: {query}."

    return {
        "final_answer": answer_text,
        "events": [
            make_event("answer", "completed", "generated grounded response")
        ],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")
    approval = state.get("approval")
    proposed_action = state.get("proposed_action")

    if approval and isinstance(approval, dict) and not approval.get("approved", True):
        comment = approval.get("comment", "Request rejected by reviewer")
        question = (
            f"Your request '{proposed_action or query}' could not be processed because it was rejected ({comment}). "
            "Please clarify or provide an alternative request."
        )
    else:
        question = f"Could you please provide more details or clarify your request: '{query}'?"

    return {
        "pending_question": question,
        "final_answer": question,
        "events": [
            make_event("clarify", "completed", "requested clarification")
        ],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    action_desc = f"Proposed sensitive action: Process side-effect for ticket request '{query}'"

    return {
        "proposed_action": action_desc,
        "events": [
            make_event("risky_action", "completed", f"action proposed: {action_desc}")
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step."""
    existing_approval = state.get("approval")
    if existing_approval and isinstance(existing_approval, dict):
        approval_data = existing_approval
    else:
        approval_data = {
            "approved": True,
            "reviewer": "mock-reviewer",
            "comment": "Approved by mock reviewer for automated execution",
        }

    return {
        "approval": approval_data,
        "events": [
            make_event(
                "approval",
                "completed",
                f"approval status: {approval_data.get('approved')}",
                approved=approval_data.get("approved"),
            )
        ],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt."""
    attempt = state.get("attempt", 0)
    new_attempt = attempt + 1
    error_msg = f"Attempt {new_attempt}: Tool execution returned ERROR or transient failure."

    return {
        "attempt": new_attempt,
        "errors": [error_msg],
        "events": [
            make_event(
                "retry",
                "completed",
                f"retry recorded: attempt {new_attempt}",
                attempt=new_attempt,
            )
        ],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded."""
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    final_msg = (
        f"We are unable to complete your request after {attempt} attempts (max {max_attempts}). "
        "Your ticket has been escalated to human support."
    )

    return {
        "final_answer": final_msg,
        "events": [
            make_event(
                "dead_letter",
                "completed",
                "request sent to dead letter queue",
                attempt=attempt,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END."""
    return {
        "events": [make_event("finalize", "completed", "workflow finished")]
    }
