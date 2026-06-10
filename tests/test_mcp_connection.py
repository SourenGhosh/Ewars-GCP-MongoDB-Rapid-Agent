import os
import asyncio
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.genai import types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()

CONNECTION_STRING = os.getenv("MONGODB_URI")
print(">>>>>>>>>>>>>>>>", CONNECTION_STRING)
root_agent = Agent(
    model="gemini-3.1-flash-lite-preview",  # Use correct model name
    name="mongodb_agent",
    instruction="""Help users query and manage MongoDB databases.
    When asked to list databases, use the available tools.""",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=[
                        "-y",
                        "mongodb-mcp-server@latest",
                    ],
                    env={
                        # Required: Use connection string instead of readOnly flag
                        "MDB_MCP_CONNECTION_STRING": CONNECTION_STRING,
                        "MDB_MCP_DEFAULT_DB": "admin",
                    },
                ),
                timeout=60,
            ),
        )
    ],
)

async def main():
    print("🚀 Starting MongoDB Agent...")
    
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="mongodb_app",
        user_id="user1",
        session_id="session1",
    )
    
    runner = Runner(
        agent=root_agent,
        app_name="mongodb_app",
        session_service=session_service,
    )
    message_query = "Find me total docs in baselines collection and also a random doc"
    message = types.Content(
        role="user",
        parts=[types.Part(text=message_query)]
    )
    
    print("\n" + "="*60)
    print(f"💬 Query: {message_query}")
    print("="*60 + "\n")
    try:
        async for event in runner.run_async(
            user_id="user1",
            session_id="session1",
            new_message=message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end='', flush=True)
                    elif part.function_response:
                        print(f"\n📊 Tool Result: {part.function_response.response}")
        
        
    except* Exception as eg:
        print("TaskGroup exception:")
        for e in eg.exceptions:
            print(repr(e))
    await runner.close()
if __name__ == "__main__":
    asyncio.run(main())