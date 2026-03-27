import logging
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from core.connection import close_pools, initialize_pools
from tools.query import register_query_tools
from tools.schema import register_schema_tools

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("postgresql_mcp")


@asynccontextmanager
async def lifespan(app):
    logger.info("Starting MCP server...")
    await initialize_pools()
    logger.info("MCP server ready")
    yield
    logger.info("Shutting down MCP server...")
    await close_pools()
    logger.info("MCP server stopped")


mcp = FastMCP("postgresql_mcp", lifespan=lifespan)

register_query_tools(mcp)
register_schema_tools(mcp)

if __name__ == "__main__":
    mcp.run()
