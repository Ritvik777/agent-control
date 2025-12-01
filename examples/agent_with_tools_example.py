"""
Practical example showing agent_control SDK with tool registration.

This example demonstrates:
1. Initializing an agent with tool schemas
2. Creating controls for different security aspects
3. Organizing controls into logical control sets
4. Creating a comprehensive policy
5. Retrieving and inspecting the agent configuration

Use case: A customer support chatbot with multiple tools
"""

import asyncio
from typing import Any

import agent_control


# Define your tools (these would be actual functions in your agent)
def search_knowledge_base(query: str) -> dict[str, Any]:
    """Search the knowledge base for relevant articles."""
    return {"results": []}


def create_support_ticket(title: str, description: str, priority: str) -> dict[str, Any]:
    """Create a new support ticket."""
    return {"ticket_id": "TICKET-123"}


def get_user_info(user_id: str) -> dict[str, Any]:
    """Retrieve user information from the database."""
    return {"user_id": user_id, "name": "John Doe"}


async def setup_customer_support_bot():
    """Set up a customer support bot with comprehensive controls."""
    
    print("=" * 70)
    print("Setting up Customer Support Bot with Agent Control")
    print("=" * 70)
    
    # Step 1: Initialize the agent with tool schemas
    print("\n[1/5] Initializing agent with tools...")
    
    # Define tool schemas for registration
    tool_schemas = [
        {
            "tool_name": "search_knowledge_base",
            "arguments": {
                "query": {
                    "type": "string",
                    "description": "Search query for knowledge base"
                }
            },
            "output_schema": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "relevance": {"type": "number"}
                        }
                    }
                }
            }
        },
        {
            "tool_name": "create_support_ticket",
            "arguments": {
                "title": {
                    "type": "string",
                    "description": "Ticket title"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed ticket description"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Ticket priority level"
                }
            },
            "output_schema": {
                "ticket_id": {"type": "string"},
                "status": {"type": "string"}
            }
        },
        {
            "tool_name": "get_user_info",
            "arguments": {
                "user_id": {
                    "type": "string",
                    "description": "User identifier"
                }
            },
            "output_schema": {
                "user_id": {"type": "string"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "account_status": {"type": "string"}
            }
        }
    ]
    
    # Initialize the agent
    agent = agent_control.init(
        agent_name="Customer Support Bot",
        agent_id="support-bot-prod-v2",
        agent_description="AI-powered customer support agent with knowledge base search and ticketing",
        agent_version="2.0.0",
        server_url="http://localhost:8000",
        tools=tool_schemas,
        # Custom metadata
        team="customer-success",
        environment="production",
        deploy_date="2025-12-01",
        max_tokens=2000
    )
    
    print(f"✓ Agent initialized: {agent.agent_name}")
    print(f"  ID: {agent.agent_id}")
    print(f"  Version: {agent.agent_version}")
    print(f"  Tools registered: {len(tool_schemas)}")
    
    # Step 2: Create controls for different security/validation aspects
    print("\n[2/5] Creating controls...")
    
    async with agent_control.AgentControlClient() as client:
        # Security controls
        print("\n  Creating security controls...")
        pii_control = await agent_control.controls.create_control(
            client,
            name="pii-detection-and-masking"
        )
        print(f"  ✓ Created: pii-detection-and-masking (ID: {pii_control['control_id']})")
        
        auth_control = await agent_control.controls.create_control(
            client,
            name="user-authentication-check"
        )
        print(f"  ✓ Created: user-authentication-check (ID: {auth_control['control_id']})")
        
        # Input validation controls
        print("\n  Creating input validation controls...")
        input_sanitization = await agent_control.controls.create_control(
            client,
            name="input-sanitization"
        )
        print(f"  ✓ Created: input-sanitization (ID: {input_sanitization['control_id']})")
        
        sql_injection_check = await agent_control.controls.create_control(
            client,
            name="sql-injection-prevention"
        )
        print(f"  ✓ Created: sql-injection-prevention (ID: {sql_injection_check['control_id']})")
        
        # Output controls
        print("\n  Creating output controls...")
        output_filtering = await agent_control.controls.create_control(
            client,
            name="output-content-filtering"
        )
        print(f"  ✓ Created: output-content-filtering (ID: {output_filtering['control_id']})")
        
        profanity_filter = await agent_control.controls.create_control(
            client,
            name="profanity-filter"
        )
        print(f"  ✓ Created: profanity-filter (ID: {profanity_filter['control_id']})")
        
        # Business logic controls
        print("\n  Creating business logic controls...")
        ticket_validation = await agent_control.controls.create_control(
            client,
            name="ticket-creation-validation"
        )
        print(f"  ✓ Created: ticket-creation-validation (ID: {ticket_validation['control_id']})")
        
        rate_limiting = await agent_control.controls.create_control(
            client,
            name="rate-limiting-check"
        )
        print(f"  ✓ Created: rate-limiting-check (ID: {rate_limiting['control_id']})")
        
        # Step 3: Organize controls into control sets
        print("\n[3/5] Creating control sets and organizing controls...")
        
        # Security control set
        print("\n  Creating security control set...")
        security_set = await agent_control.control_sets.create_control_set(
            client,
            name="security-controls-set"
        )
        security_set_id = security_set["control_set_id"]
        print(f"  ✓ Created: security-controls-set (ID: {security_set_id})")
        
        await agent_control.control_sets.add_control_to_control_set(
            client, security_set_id, pii_control["control_id"]
        )
        await agent_control.control_sets.add_control_to_control_set(
            client, security_set_id, auth_control["control_id"]
        )
        print(f"    Added 2 controls to security set")
        
        # Input validation control set
        print("\n  Creating input validation control set...")
        input_set = await agent_control.control_sets.create_control_set(
            client,
            name="input-validation-set"
        )
        input_set_id = input_set["control_set_id"]
        print(f"  ✓ Created: input-validation-set (ID: {input_set_id})")
        
        await agent_control.control_sets.add_control_to_control_set(
            client, input_set_id, input_sanitization["control_id"]
        )
        await agent_control.control_sets.add_control_to_control_set(
            client, input_set_id, sql_injection_check["control_id"]
        )
        print(f"    Added 2 controls to input validation set")
        
        # Output control set
        print("\n  Creating output filtering control set...")
        output_set = await agent_control.control_sets.create_control_set(
            client,
            name="output-filtering-set"
        )
        output_set_id = output_set["control_set_id"]
        print(f"  ✓ Created: output-filtering-set (ID: {output_set_id})")
        
        await agent_control.control_sets.add_control_to_control_set(
            client, output_set_id, output_filtering["control_id"]
        )
        await agent_control.control_sets.add_control_to_control_set(
            client, output_set_id, profanity_filter["control_id"]
        )
        print(f"    Added 2 controls to output filtering set")
        
        # Business logic control set
        print("\n  Creating business logic control set...")
        business_set = await agent_control.control_sets.create_control_set(
            client,
            name="business-logic-set"
        )
        business_set_id = business_set["control_set_id"]
        print(f"  ✓ Created: business-logic-set (ID: {business_set_id})")
        
        await agent_control.control_sets.add_control_to_control_set(
            client, business_set_id, ticket_validation["control_id"]
        )
        await agent_control.control_sets.add_control_to_control_set(
            client, business_set_id, rate_limiting["control_id"]
        )
        print(f"    Added 2 controls to business logic set")
        
        # Step 4: Create policy and associate all control sets
        print("\n[4/5] Creating comprehensive policy...")
        
        policy = await agent_control.policies.create_policy(
            client,
            name="customer-support-production-policy"
        )
        policy_id = policy["policy_id"]
        print(f"✓ Created policy: customer-support-production-policy (ID: {policy_id})")
        
        # Add all control sets to policy
        print("\n  Adding control sets to policy...")
        await agent_control.policies.add_control_set_to_policy(
            client, policy_id, security_set_id
        )
        print(f"  ✓ Added security control set")
        
        await agent_control.policies.add_control_set_to_policy(
            client, policy_id, input_set_id
        )
        print(f"  ✓ Added input validation control set")
        
        await agent_control.policies.add_control_set_to_policy(
            client, policy_id, output_set_id
        )
        print(f"  ✓ Added output filtering control set")
        
        await agent_control.policies.add_control_set_to_policy(
            client, policy_id, business_set_id
        )
        print(f"  ✓ Added business logic control set")
        
        # Step 5: Verify the configuration
        print("\n[5/5] Verifying agent configuration...")
        
        # Get agent details
        agent_data = await agent_control.agents.get_agent(
            client,
            str(agent.agent_id)
        )
        
        print(f"\n✓ Agent verification complete:")
        print(f"  Name: {agent_data['agent']['agent_name']}")
        print(f"  ID: {agent_data['agent']['agent_id']}")
        print(f"  Version: {agent_data['agent']['agent_version']}")
        print(f"  Description: {agent_data['agent']['agent_description']}")
        
        print(f"\n  Registered Tools ({len(agent_data['tools'])}):")
        for tool in agent_data['tools']:
            print(f"    • {tool['tool_name']}")
        
        # Get policy details
        policy_control_sets = await agent_control.policies.list_policy_control_sets(
            client,
            policy_id=policy_id
        )
        print(f"\n  Policy Control Sets ({len(policy_control_sets['control_set_ids'])}):")
        print(f"    Control Set IDs: {policy_control_sets['control_set_ids']}")
        
    # Summary
    print("\n" + "=" * 70)
    print("SETUP COMPLETE!")
    print("=" * 70)
    print(f"""
Your customer support bot is now configured with:

📊 Agent Details:
   • Name: {agent.agent_name}
   • ID: {agent.agent_id}
   • Version: {agent.agent_version}
   • Tools: {len(tool_schemas)} registered

🛡️ Security Controls:
   • PII detection and masking
   • User authentication check

✅ Input Validation:
   • Input sanitization
   • SQL injection prevention

🔍 Output Filtering:
   • Content filtering
   • Profanity filter

📋 Business Logic:
   • Ticket creation validation
   • Rate limiting

📜 Policy: customer-support-production-policy
   • 4 control sets with 8 total controls

Next Steps:
1. Add specific rules to each control
2. Assign the policy to your agent
3. Use the evaluation API to enforce controls at runtime
4. Monitor agent behavior through the server dashboard
    """)


async def main():
    """Main entry point."""
    try:
        await setup_customer_support_bot()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  • Is the Agent Control server running at http://localhost:8000?")
        print("  • Check server logs for errors")
        print("  • Verify network connectivity")
        raise


if __name__ == "__main__":
    asyncio.run(main())

