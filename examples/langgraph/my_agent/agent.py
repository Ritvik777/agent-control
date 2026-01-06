"""
LangGraph Agent with Agent Protect integration.

This module demonstrates how to build a LangGraph agent that uses
Agent Protect to validate user inputs for safety before processing.
"""

import asyncio
import os
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

# Optional: Import agent_control if available
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdks/python/src"))
    from agent_control import AgentControlClient
    AGENT_PROTECT_AVAILABLE = True
except ImportError:
    AGENT_PROTECT_AVAILABLE = False
    print("Warning: Agent Protect not available. Safety checks will be skipped.")


class AgentState(TypedDict):
    """
    The state of the agent.

    Attributes:
        messages: The conversation history
        safety_check_passed: Whether the input passed safety checks
        safety_reason: Reason for safety check result
    """
    messages: Annotated[list[BaseMessage], add_messages]
    safety_check_passed: bool
    safety_reason: str


async def safety_check_node(state: AgentState) -> dict:
    """
    Check if the user's input is safe using Agent Protect.

    Args:
        state: The current agent state

    Returns:
        Updated state with safety check results
    """
    # Get the last user message
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not last_message or not isinstance(last_message, HumanMessage):
        return {
            "safety_check_passed": True,
            "safety_reason": "No user input to check"
        }

    user_content = last_message.content

    # If Agent Protect is not available, skip check
    if not AGENT_PROTECT_AVAILABLE:
        return {
            "safety_check_passed": True,
            "safety_reason": "Agent Protect not configured"
        }

    # Check with Agent Control server
    try:
        import uuid as uuid_module

        agent_control_url = os.getenv("AGENT_CONTROL_URL", "http://localhost:8000")
        # Generate a deterministic agent UUID for this demo
        agent_uuid = str(uuid_module.uuid5(uuid_module.NAMESPACE_DNS, "langgraph-demo-agent"))

        async with AgentControlClient(base_url=agent_control_url) as client:
            # Call the evaluation endpoint
            response = await client.http_client.post(
                "/api/v1/evaluation",
                json={
                    "agent_uuid": agent_uuid,
                    "payload": {"input": str(user_content)},
                    "check_stage": "pre"
                }
            )
            response.raise_for_status()
            result = response.json()

            is_safe = result.get("is_safe", True)
            matches = result.get("matches", [])
            reason = "Content passed safety checks"

            if not is_safe and matches:
                # Get the reason from the first match
                first_match = matches[0]
                reason = first_match.get("result", {}).get("message", "Content failed safety checks")

            return {
                "safety_check_passed": is_safe,
                "safety_reason": reason
            }
    except Exception as e:
        print(f"Safety check error: {e}")
        # On error, allow but log
        return {
            "safety_check_passed": True,
            "safety_reason": f"Safety check failed: {str(e)}"
        }


def should_continue(state: AgentState) -> str:
    """
    Determine if the agent should continue processing or end.

    Args:
        state: The current agent state

    Returns:
        The next node to execute
    """
    if not state.get("safety_check_passed", True):
        return "reject"
    return "process"


def reject_node(state: AgentState) -> dict:
    """
    Handle rejected inputs that failed safety checks.

    Args:
        state: The current agent state

    Returns:
        Updated state with rejection message
    """
    reason = state.get("safety_reason", "Content failed safety checks")
    rejection_message = AIMessage(
        content=f"I'm sorry, but I can't process that request. Reason: {reason}"
    )

    return {
        "messages": [rejection_message]
    }


async def agent_node(state: AgentState) -> dict:
    """
    The main agent processing node.

    Args:
        state: The current agent state

    Returns:
        Updated state with agent response
    """
    messages = state["messages"]

    # Initialize the LLM
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7
    )

    # Get response from the model
    response = await model.ainvoke(messages)

    return {
        "messages": [response]
    }


def create_graph() -> StateGraph:
    """
    Create the LangGraph workflow.

    Returns:
        Compiled LangGraph workflow
    """
    # Initialize the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("safety_check", safety_check_node)
    workflow.add_node("reject", reject_node)
    workflow.add_node("agent", agent_node)

    # Set entry point
    workflow.set_entry_point("safety_check")

    # Add conditional edges
    workflow.add_conditional_edges(
        "safety_check",
        should_continue,
        {
            "reject": "reject",
            "process": "agent"
        }
    )

    # Add edges to END
    workflow.add_edge("reject", END)
    workflow.add_edge("agent", END)

    # Compile the graph
    return workflow.compile()


# Create the graph instance
graph = create_graph()


async def run_agent(user_input: str) -> str:
    """
    Run the agent with a user input.

    Args:
        user_input: The user's message

    Returns:
        The agent's response
    """
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "safety_check_passed": True,
        "safety_reason": ""
    }

    result = await graph.ainvoke(initial_state)

    # Get the last message
    messages = result["messages"]
    if messages:
        last_message = messages[-1]
        return last_message.content

    return "No response generated"


# Example usage
if __name__ == "__main__":
    async def main():
        """Main function to demonstrate the agent."""
        from dotenv import load_dotenv
        load_dotenv()

        print("🤖 LangGraph Agent with Agent Protect")
        print("=" * 50)
        print()

        # Test cases
        test_inputs = [
            "Hello! Can you help me with a Python question?",
            "What's the weather like today?",
            "Tell me about LangGraph and LangChain.",
        ]

        for user_input in test_inputs:
            print(f"User: {user_input}")
            response = await run_agent(user_input)
            print(f"Agent: {response}")
            print()

    asyncio.run(main())

