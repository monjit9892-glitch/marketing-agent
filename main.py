from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Initialize model
model = ChatOpenAI(model="gpt-4")

# MCP server parameters
server_params = StdioServerParameters(
    command="npx",
    args=["@brightdata/mcp"],
    env={
        "API_TOKEN": os.getenv("API_TOKEN"),
        "WEB_UNLOCKER_ZONE": os.getenv("WEB_UNLOCKER_ZONE"),
        "BROWSER_ZONE": os.getenv("BROWSER_ZONE"),
        "BROWSER_AUTH": os.getenv("BROWSER_AUTH"),
    },
)


from dotenv import load_dotenv
from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from pydantic_core import ValidationError
from typing_extensions import TypedDict
from web_operation import web_search as web_search_api
from pydantic import BaseModel, Field
import json
import re
from prompt import (
    EXTRACT_CONTENT_SYSTEM_PROMPT,
    EMAIL_CRAFTING_SYSTEM_PROMPT
)


load_dotenv()
llm = init_chat_model("gpt-4o")


# ------------------- State -------------------
class State(TypedDict):
    messages: Annotated[list, add_messages]
    user_question: str | None
    company_info: dict | None
    email_text: str | None

# ------------------- Pydantic Schema -------------------
class EmailSchema(BaseModel):
    subject: str = Field(..., description="The subject line of the email")
    body: str = Field(..., description="The main body of the email")
    

# ------------------- Nodes -------------------
def company_info_node(state: State):
    """Search web, analyze results & extract structured company info."""
    query = state.get("user_question", "")
    print(f"🔍 Searching Web for: {query}")

    web_results = web_search_api(query) or []
    print(f"✅ Results fetched: {len(web_results)}")
    if not web_results:
        return {"company_info": {}}

    messages = [
        {"role": "system", "content": EXTRACT_CONTENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"User asked: {query}\n\nSearch Results:\n{json.dumps(web_results, indent=2)}"}
    ]
    reply = llm.invoke(messages)
    print("🔎 Raw LLM Output received")

    raw_text = reply.content
    try:
        match = re.search(r"```json(.*?)```", raw_text, re.DOTALL) or re.search(r"(\{.*\})", raw_text, re.DOTALL)
        cleaned = match.group(1).strip() if match else raw_text.strip()
        company_info = json.loads(cleaned)
    except Exception as e:
        print(f"⚠️ JSON parsing failed: {e}")
        company_info = {"raw_output": raw_text}

    return {"company_info": company_info}


def generate_email_node(state: State, mail_type: str = "product_updates"):
    """
    Generate email from company info for a given mail type.
    
    mail_type can be:
    'product_updates', 'promotions', 'order_reorder', 'event_driven',
    'customer_relationship', 'educational_content', 'transactional', 'b2b_programs'
    """
    print(f"✉️ Generating '{mail_type}' email from company info")
    company_info = state.get("company_info", {})

    if not company_info:
        return {"email_text": "No company info available to generate email."}

    # Dynamically create the system prompt including the selected type
    system_prompt = f"{EMAIL_CRAFTING_SYSTEM_PROMPT}\nSelected email type: {mail_type}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Company info:\n{json.dumps(company_info, indent=2)}"}
    ]

    reply = llm.invoke(messages)
    raw_text = reply.content

    try:
        # Extract JSON part
        match = re.search(r"```json(.*?)```", raw_text, re.DOTALL) or re.search(r"(\{.*\})", raw_text, re.DOTALL)
        cleaned = match.group(1).strip() if match else raw_text.strip()
        parsed = json.loads(cleaned)

        # ✅ Validate using Pydantic (subject and body only)
        email_obj = EmailSchema(**parsed)

        # Format nicely for printing
        email_text = f"Subject: {email_obj.subject}\n\n{email_obj.body}"

    except (json.JSONDecodeError, ValidationError) as e:
        print(f"⚠️ Failed to parse/validate email: {e}")
        email_text = raw_text  # fallback to raw text

    return {"email_text": email_text}




# ------------------- Research Agent -------------------
research_builder = StateGraph(State)
research_builder.add_node("company_info", company_info_node)
research_builder.add_edge(START, "company_info")
research_builder.add_edge("company_info", END)
research_agent = research_builder.compile()


# ------------------- Email Agent -------------------
email_builder = StateGraph(State)
email_builder.add_node("generate_email", generate_email_node)
email_builder.add_edge(START, "generate_email")
email_builder.add_edge("generate_email", END)
email_agent = email_builder.compile()


# ------------------- CLI -------------------
def run_agents():
    print("💻 Marketing-AgenticAI")
    print("Type 'exit' to quit\n")

    # List of available email types
    email_types = {
        "1": "product_updates",
        "2": "promotions",
        "3": "order_reorder",
        "4": "event_driven",
        "5": "customer_relationship",
        "6": "educational_content",
        "7": "transactional",
        "8": "b2b_programs"
    }

    while True:
        user_input = input("Enter Company/person/Buyer to search: ")
        if user_input.lower() == "exit":
            print("👋 Bye")
            break

        # Step 1: Research Agent
        state = {
            "messages": [{"role": "user", "content": user_input}],
            "user_question": user_input,
            "company_info": None,
            "email_text": None,
        }

        print("\n🚀 Running Research Agent...")
        research_state = research_agent.invoke(state)

        print("\n📊 Company Info:")
        print(json.dumps(research_state.get("company_info"), indent=2))

        # Ask for email type
        print("\nSelect Email Type (press Enter for default: New Collection Launches):")
        for k, v in email_types.items():
            print(f"{k}. {v.replace('_', ' ').title()}")
        mail_type_input = input("Enter type number: ").strip()

        # Default to "product_updates" if no input or invalid
        mail_type = email_types.get(mail_type_input, "product_updates")

        # Step 2: Email Agent
        print(f"\n✉️ Running Email Agent for type: {mail_type.replace('_', ' ').title()}...")
        email_state = generate_email_node(research_state, mail_type=mail_type)

        print("\n✉️ Generated Email:\n")
        print(email_state.get("email_text"))
        print("-" * 80)


if __name__ == "__main__":
    run_agents()



def extract_ai_content(agent_response):
    if isinstance(agent_response, dict) and "messages" in agent_response:
        for msg in reversed(agent_response["messages"]):
            if getattr(msg, "content", None):
                return msg.content
    return str(agent_response)

async def run_multi_agent():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)

            # Agent 1: Info extractor
            agent1 = create_react_agent(model, tools)
            
            # Agent 2: Email crafter
            agent2 = create_react_agent(model, tools)

            company_name = "Atelier Interiors"

            # --- Agent 1: Process user input ---
            agent1_resp = await agent1.ainvoke({
                "messages": [
                    {"role": "system", "content": EXTRACT_CONTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": company_name}
                ]
            })
            agent1_output = extract_ai_content(agent1_resp)
            print(f"Agent 1 Output: {agent1_output}")

            # --- Agent 2: Craft email from Agent 1 output ---
            agent2_resp = await agent2.ainvoke({
                "messages": [
                    {"role": "system", "content": EMAIL_CRAFTING_SYSTEM_PROMPT},
                    {"role": "user", "content": agent1_output}
                ]
            })
            email_output = extract_ai_content(agent2_resp)
            print(f"\n✉️ Email:\n{email_output}\n")

if __name__ == "__main__":
    asyncio.run(run_multi_agent())