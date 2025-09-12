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


EXTRACT_CONTENT_SYSTEM_PROMPT = f"""
You are a helpful research assistant that extracts who will research about a given company and find out details about the company, what they specialize in, 
the type of products they sell, and the type of services they offer. Find out useful info about their market segment, what their competitors are, and what their strengths and weaknesses are.
"""

EMAIL_CRAFTING_SYSTEM_PROMPT = f"""
You are a helpful email crafting assistant that crafts an email subject and body from input.
Your role is to craft an email based on the data that you have received from the research assistant.
The goal of the email is to sell some ecommerce products to the company and get them to buy from you based on their needs.
"""

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