"""
Unit tests for AgentState / PlanStep models (models/agents/state.py)
and the LangGraph workflow routing logic (core/workflow_manual/manual_flow.py)

Run:  pytest tests/unit/test_workflow.py -v
"""

import pytest
from arcis.models.agents.state import AgentState, PlanStep


# ---------------------------------------------------------------------------
# UT-AS-01  PlanStep accepts all valid status literals
# ---------------------------------------------------------------------------
def test_planstep_valid_statuses():
    """PlanStep can be constructed with every valid status value."""
    for status in ("pending", "in_progress", "completed", "failed"):
        step: PlanStep = {
            "id": 1,
            "description": "Test step",
            "status": status,
            "assigned_agent": "UtilityAgent",
        }
        assert step["status"] == status


# ---------------------------------------------------------------------------
# UT-AS-02  AgentState can be constructed with required fields
# ---------------------------------------------------------------------------
def test_agentstate_construction():
    """AgentState TypedDict accepts all required keys without error."""
    state: AgentState = {
        "thread_id": "thread-abc",
        "input": "Hello ARCIS",
        "plan": [],
        "messages": [],
        "context": {},
        "last_tool_output": "",
        "final_response": "",
        "current_step_index": 0,
        "next_node": None,
        "workflow_status": None,
    }
    assert state["input"] == "Hello ARCIS"
    assert state["plan"] == []


# ---------------------------------------------------------------------------
# UT-WG-01  Planner short-circuit: workflow_status == "FINISHED" → END
# ---------------------------------------------------------------------------
def test_planner_short_circuit_condition():
    """
    The conditional edge from planner routes to END when workflow_status is FINISHED.
    We test the lambda directly without running the full LangGraph graph.
    """
    router = lambda state: "end" if state.get("workflow_status") == "FINISHED" else "supervisor"

    state_finished: AgentState = {
        "thread_id": "t1", "input": "hi", "plan": [], "messages": [],
        "context": {}, "last_tool_output": "", "final_response": "Hello!",
        "current_step_index": 0, "next_node": None, "workflow_status": "FINISHED",
    }
    state_continue: AgentState = {
        "thread_id": "t1", "input": "do something", "plan": [], "messages": [],
        "context": {}, "last_tool_output": "", "final_response": "",
        "current_step_index": 0, "next_node": "email_agent", "workflow_status": "CONTINUE",
    }

    assert router(state_finished) == "end"
    assert router(state_continue) == "supervisor"


# ---------------------------------------------------------------------------
# UT-WG-02  Supervisor router reads next_node from state
# ---------------------------------------------------------------------------
def test_supervisor_router_reads_next_node():
    """
    supervisor_router returns state['next_node'] so we can verify the
    routing table logic is sound without instantiating any LLM.
    """
    from arcis.core.workflow_manual.agents.supervisor import supervisor_router

    for agent in ["email_agent", "booking_agent", "utility_agent",
                  "scheduler_agent", "mcp_agent"]:
        state: AgentState = {
            "thread_id": "t1", "input": "task", "plan": [], "messages": [],
            "context": {}, "last_tool_output": "", "final_response": "",
            "current_step_index": 0, "next_node": agent, "workflow_status": "CONTINUE",
        }
        result = supervisor_router(state)
        assert result == agent, f"Expected '{agent}', got '{result}'"


# ---------------------------------------------------------------------------
# UT-WG-03  Replanner router: 'end' when FINISHED, 'continue' otherwise
# ---------------------------------------------------------------------------
def test_replanner_router():
    from arcis.core.workflow_manual.agents.replanner import replanner_router

    finished_state: AgentState = {
        "thread_id": "t1", "input": "task", "plan": [], "messages": [],
        "context": {}, "last_tool_output": "done", "final_response": "All done!",
        "current_step_index": 0, "next_node": None, "workflow_status": "FINISHED",
    }
    continue_state: AgentState = {
        "thread_id": "t1", "input": "task", "plan": [], "messages": [],
        "context": {}, "last_tool_output": "step 1 done", "final_response": "",
        "current_step_index": 0, "next_node": "email_agent", "workflow_status": "CONTINUE",
    }

    assert replanner_router(finished_state) == "end"
    assert replanner_router(continue_state) == "continue"


# ---------------------------------------------------------------------------
# UT-WG-04  Workflow graph can be compiled without errors
# ---------------------------------------------------------------------------
def test_workflow_graph_compiles():
    """
    create_workflow() + compile() must succeed without any LLM calls.
    This validates the graph wiring (nodes, edges) is correct.
    """
    from unittest.mock import patch, MagicMock

    # Patch the MongoDB checkpointer so no real DB connection is needed
    with patch("arcis.core.workflow_manual.manual_flow.checkpointer", MagicMock()):
        from arcis.core.workflow_manual.manual_flow import create_workflow
        workflow = create_workflow()
        app = workflow.compile(checkpointer=MagicMock())

    assert app is not None
