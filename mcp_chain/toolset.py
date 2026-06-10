# mcp/toolset.py — REPLACE entire file

import os
from dotenv import load_dotenv
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()

# Create ONE shared toolset instance at module level.
# All agents import and share this — only ONE npx subprocess spawned.
_shared_read_toolset: McpToolset | None = None
_shared_write_toolset: McpToolset | None = None


def get_mongo_toolset(read_only: bool = True) -> McpToolset:
    """
    Returns a shared McpToolset instance.
    First call spawns the subprocess. Subsequent calls reuse it.
    This eliminates per-agent cold start overhead (~8s × 6 = 48s saved).
    """
    global _shared_read_toolset, _shared_write_toolset

    connection_string = os.getenv("MONGODB_URI")
    if not connection_string:
        raise ValueError("MONGODB_URI not set in environment")

    if read_only:
        if _shared_read_toolset is None:
            _shared_read_toolset = McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="npx",
                        args=["-y", "mongodb-mcp-server@latest", "--readOnly"],
                        env={
                            "MDB_MCP_CONNECTION_STRING": connection_string,
                            "MDB_MCP_DEFAULT_DB": "ewars_db",
                        },
                    ),
                    timeout=30,
                )
            )
        return _shared_read_toolset
    else:
        if _shared_write_toolset is None:
            _shared_write_toolset = McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="npx",
                        args=["-y", "mongodb-mcp-server@latest"],
                        env={
                            "MDB_MCP_CONNECTION_STRING": connection_string,
                            "MDB_MCP_DEFAULT_DB": "ewars_db",
                        },
                    ),
                    timeout=30,
                )
            )
        return _shared_write_toolset