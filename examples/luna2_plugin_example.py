"""Example: Using Galileo Luna-2 Plugin with Agent Control.

This example demonstrates how to use the Luna-2 plugin for runtime protection
of AI agents using Galileo's enterprise metrics.

Installation:
    pip install agent-control[luna2]

Environment Variables:
    GALILEO_API_KEY=your-api-key
    GALILEO_PROJECT=your-project-name (optional, can be set in code)

Documentation:
    https://v2docs.galileo.ai/concepts/protect/overview
"""

import asyncio
import os
from agent_control import AgentControlClient


async def example_local_stage_toxicity():
    """Example 1: Local stage with input toxicity check.
    
    Local stages allow you to define rules at runtime with full control.
    Changes to thresholds can be made without redeploying your application.
    """
    print("\n=== Example 1: Local Stage - Input Toxicity ===\n")
    
    # Initialize client
    client = AgentControlClient(base_url=os.getenv("AGENT_CONTROL_URL", "http://localhost:8000"))
    
    # Create an agent
    agent_response = await client.agents.create_agent(
        name="chatbot-with-luna2",
        description="Chatbot protected by Galileo Luna-2",
    )
    agent_id = agent_response["agent_id"]
    print(f"Created agent: {agent_id}")
    
    # Create control with Luna-2 plugin (local stage)
    control_response = await client.controls.create_control(
        agent_id=agent_id,
        name="block-toxic-inputs",
        control_definition={
            "description": "Block toxic user inputs using Luna-2",
            "enabled": True,
            "applies_to": "llm_call",
            "check_stage": "pre",  # Check before LLM call
            "selector": {"path": "input"},
            "evaluator": {
                "type": "plugin",
                "config": {
                    "plugin_name": "galileo-luna2",
                    "plugin_config": {
                        # Local stage: Define rules at runtime
                        "stage_type": "local",
                        "metric": "input_toxicity",
                        "operator": "gt",
                        "target_value": 0.8,
                        "galileo_project": os.getenv("GALILEO_PROJECT", "chatbot-demo"),
                        "timeout": 5.0,
                        "on_error": "allow",  # Fail open on errors
                    }
                }
            },
            "action": {"decision": "deny"},
            "tags": ["safety", "luna2", "toxicity"],
        }
    )
    control_id = control_response["control_id"]
    print(f"Created control: {control_id}")
    
    # Test evaluation with safe input
    print("\n--- Testing safe input ---")
    safe_result = await client.evaluation.evaluate_interaction(
        agent_id=agent_id,
        interaction_type="llm_call",
        stage="pre",
        payload={"input": "Hello, how are you today?"}
    )
    print(f"Safe input result: {safe_result['decision']}")
    print(f"Triggered controls: {len(safe_result.get('triggered_controls', []))}")
    
    # Test evaluation with toxic input
    print("\n--- Testing toxic input ---")
    toxic_result = await client.evaluation.evaluate_interaction(
        agent_id=agent_id,
        interaction_type="llm_call",
        stage="pre",
        payload={"input": "You're an idiot and I hate you!"}
    )
    print(f"Toxic input result: {toxic_result['decision']}")
    print(f"Triggered controls: {len(toxic_result.get('triggered_controls', []))}")
    if toxic_result.get('triggered_controls'):
        for control in toxic_result['triggered_controls']:
            print(f"  - {control['control_name']}: {control['result']['message']}")
    
    # Update threshold on the fly (no code deployment needed!)
    print("\n--- Updating threshold to be more strict ---")
    await client.controls.update_control(
        control_id=control_id,
        control_definition={
            "evaluator": {
                "type": "plugin",
                "config": {
                    "plugin_name": "galileo-luna2",
                    "plugin_config": {
                        "stage_type": "local",
                        "metric": "input_toxicity",
                        "operator": "gt",
                        "target_value": 0.5,  # More strict!
                        "galileo_project": os.getenv("GALILEO_PROJECT", "chatbot-demo"),
                    }
                }
            }
        }
    )
    print("Updated threshold to 0.5 (from 0.8)")
    
    # Test again - same input might now be blocked
    print("\n--- Testing with new threshold ---")
    result = await client.evaluation.evaluate_interaction(
        agent_id=agent_id,
        interaction_type="llm_call",
        stage="pre",
        payload={"input": "This is slightly annoying."}
    )
    print(f"Moderately negative input: {result['decision']}")


async def example_central_stage():
    """Example 2: Central stage managed in Galileo.
    
    Central stages are managed by AI governance teams in Galileo.
    They can be updated without any code changes in your application.
    """
    print("\n=== Example 2: Central Stage - Managed Protection ===\n")
    
    client = AgentControlClient(base_url=os.getenv("AGENT_CONTROL_URL", "http://localhost:8000"))
    
    # Create agent
    agent_response = await client.agents.create_agent(
        name="enterprise-chatbot",
        description="Chatbot using centrally managed protection",
    )
    agent_id = agent_response["agent_id"]
    print(f"Created agent: {agent_id}")
    
    # Create control that references a central stage
    control_response = await client.controls.create_control(
        agent_id=agent_id,
        name="enterprise-protection",
        control_definition={
            "description": "Use enterprise-wide protection rules",
            "enabled": True,
            "applies_to": "llm_call",
            "check_stage": "pre",
            "selector": {"path": "input"},
            "evaluator": {
                "type": "plugin",
                "config": {
                    "plugin_name": "galileo-luna2",
                    "plugin_config": {
                        # Central stage: Reference pre-defined stage
                        "stage_type": "central",
                        "stage_name": "enterprise-chatbot-input-protection",
                        "stage_version": 2,  # Optional: pin to specific version
                        "galileo_project": os.getenv("GALILEO_PROJECT", "enterprise"),
                        "timeout": 10.0,
                    }
                }
            },
            "action": {"decision": "deny"},
            "tags": ["governance", "luna2", "central"],
        }
    )
    print(f"Created control: {control_response['control_id']}")
    print("Note: Rules are managed in Galileo console by AI governance team")


async def example_pii_detection():
    """Example 3: PII detection using Luna-2.
    
    Detect and block sensitive information like SSNs, credit cards, etc.
    """
    print("\n=== Example 3: PII Detection ===\n")
    
    client = AgentControlClient(base_url=os.getenv("AGENT_CONTROL_URL", "http://localhost:8000"))
    
    # Create agent
    agent_response = await client.agents.create_agent(
        name="pii-protected-agent",
        description="Agent with PII protection",
    )
    agent_id = agent_response["agent_id"]
    print(f"Created agent: {agent_id}")
    
    # Create PII detection control
    control_response = await client.controls.create_control(
        agent_id=agent_id,
        name="pii-detector",
        control_definition={
            "description": "Detect PII in user inputs",
            "enabled": True,
            "applies_to": "llm_call",
            "check_stage": "pre",
            "selector": {"path": "input"},
            "evaluator": {
                "type": "plugin",
                "config": {
                    "plugin_name": "galileo-luna2",
                    "plugin_config": {
                        "stage_type": "local",
                        "metric": "pii_detection",
                        "operator": "contains",
                        "target_value": ["ssn", "credit_card", "password"],
                        "galileo_project": os.getenv("GALILEO_PROJECT", "pii-demo"),
                    }
                }
            },
            "action": {"decision": "deny"},
            "tags": ["pii", "compliance"],
        }
    )
    print(f"Created PII control: {control_response['control_id']}")
    
    # Test with PII
    print("\n--- Testing input with SSN ---")
    result = await client.evaluation.evaluate_interaction(
        agent_id=agent_id,
        interaction_type="llm_call",
        stage="pre",
        payload={"input": "My SSN is 123-45-6789"}
    )
    print(f"Result: {result['decision']}")


async def example_output_hallucination():
    """Example 4: Output hallucination check.
    
    Check LLM outputs for hallucinations using Luna-2.
    """
    print("\n=== Example 4: Output Hallucination Check ===\n")
    
    client = AgentControlClient(base_url=os.getenv("AGENT_CONTROL_URL", "http://localhost:8000"))
    
    # Create agent
    agent_response = await client.agents.create_agent(
        name="rag-chatbot",
        description="RAG chatbot with hallucination detection",
    )
    agent_id = agent_response["agent_id"]
    print(f"Created agent: {agent_id}")
    
    # Create hallucination check control
    control_response = await client.controls.create_control(
        agent_id=agent_id,
        name="hallucination-detector",
        control_definition={
            "description": "Detect hallucinations in LLM outputs",
            "enabled": True,
            "applies_to": "llm_call",
            "check_stage": "post",  # Check AFTER LLM responds
            "selector": {"path": "output"},
            "evaluator": {
                "type": "plugin",
                "config": {
                    "plugin_name": "galileo-luna2",
                    "plugin_config": {
                        "stage_type": "local",
                        "metric": "output_hallucination",
                        "operator": "gt",
                        "target_value": 0.7,
                        "galileo_project": os.getenv("GALILEO_PROJECT", "rag-demo"),
                    }
                }
            },
            "action": {"decision": "warn"},  # Warn but allow
            "tags": ["hallucination", "quality"],
        }
    )
    print(f"Created hallucination control: {control_response['control_id']}")
    
    # Test with potentially hallucinated output
    print("\n--- Testing LLM output ---")
    result = await client.evaluation.evaluate_interaction(
        agent_id=agent_id,
        interaction_type="llm_call",
        stage="post",
        payload={
            "input": "What is the capital of France?",
            "output": "The capital of France is Berlin."  # Hallucination!
        }
    )
    print(f"Result: {result['decision']}")
    print(f"Warnings: {len(result.get('warnings', []))}")


async def example_multi_metric():
    """Example 5: Multiple Luna-2 metrics in one agent.
    
    Combine multiple protection layers with different Luna-2 metrics.
    """
    print("\n=== Example 5: Multi-Metric Protection ===\n")
    
    client = AgentControlClient(base_url=os.getenv("AGENT_CONTROL_URL", "http://localhost:8000"))
    
    # Create agent
    agent_response = await client.agents.create_agent(
        name="fully-protected-agent",
        description="Agent with comprehensive Luna-2 protection",
    )
    agent_id = agent_response["agent_id"]
    print(f"Created agent: {agent_id}")
    
    # Add multiple controls with different metrics
    metrics = [
        ("input_toxicity", "gt", 0.8, "deny"),
        ("prompt_injection", "gt", 0.9, "deny"),
        ("input_sexism", "gt", 0.7, "deny"),
        ("pii_detection", "contains", ["ssn", "credit_card"], "deny"),
    ]
    
    for metric, operator, target, action in metrics:
        control_response = await client.controls.create_control(
            agent_id=agent_id,
            name=f"check-{metric}",
            control_definition={
                "description": f"Check {metric} using Luna-2",
                "enabled": True,
                "applies_to": "llm_call",
                "check_stage": "pre",
                "selector": {"path": "input"},
                "evaluator": {
                    "type": "plugin",
                    "config": {
                        "plugin_name": "galileo-luna2",
                        "plugin_config": {
                            "stage_type": "local",
                            "metric": metric,
                            "operator": operator,
                            "target_value": target,
                            "galileo_project": os.getenv("GALILEO_PROJECT", "multi-demo"),
                        }
                    }
                },
                "action": {"decision": action},
                "tags": ["luna2", metric],
            }
        )
        print(f"Added control: {metric}")
    
    print(f"\nAgent now has {len(metrics)} Luna-2 protection layers")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Galileo Luna-2 Plugin Examples")
    print("=" * 60)
    
    # Check environment
    if not os.getenv("GALILEO_API_KEY"):
        print("\n⚠️  Warning: GALILEO_API_KEY not set!")
        print("Set it with: export GALILEO_API_KEY=your-api-key")
        print("Get your key from: https://app.galileo.ai\n")
        return
    
    # Run examples
    await example_local_stage_toxicity()
    await example_central_stage()
    await example_pii_detection()
    await example_output_hallucination()
    await example_multi_metric()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

