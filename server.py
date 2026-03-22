from mcp.server.fastmcp import FastMCP
from contextlib import asynccontextmanager
from core.connection import get_pool, close_pool
from tools.query import register_query_tools
from tools.schema import register_schema_tools
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app):
    await get_pool()          # Inicializa o pool na startup
    yield
    await close_pool()        # Fecha na shutdown

mcp = FastMCP("postgresql_mcp", lifespan=lifespan)

register_query_tools(mcp)
register_schema_tools(mcp)

if __name__ == "__main__":
    mcp.run()                 # stdio (padrão para Claude Desktop)
    # mcp.run(transport="streamable_http", port=8000)  # Para o Axis via HTTP