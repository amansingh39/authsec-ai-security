# server.py
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from authsec_sdk import from_env, mount_mcp, ManifestTool
from dotenv import load_dotenv

mcp = FastMCP("my-server")

@mcp.tool()
def add_no(a: float, b: float) -> float:
    return a + b

@mcp.tool()
def multiply_no(a: float, b: float) -> float:
    return a * b

def my_tools():
    return [
        ManifestTool(
            name="add_no",
            description="Add two numbers",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
        ),
        ManifestTool(
            name="multiply_no",
            description="Multiply two numbers",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
        ),
    ]

load_dotenv()
cfg = from_env()                       # reads all AUTHSEC_* vars from step 3
cfg.tool_inventory_provider = my_tools # explicit manifest for the dashboard

app = FastAPI()
mount_mcp(app, "/mcp", mcp, cfg)       # ← the entire integration is this line
