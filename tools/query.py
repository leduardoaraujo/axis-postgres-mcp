import logging
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from core.connection import get_pool
from core.formatters import records_to_dict, format_as_markdown_table, format_as_json
from enum import Enum

logger = logging.getLogger(__name__)

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

class ExecuteQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sql: str = Field(
        ...,
        description="SQL SELECT to execute. Enforced read-only at the DB role level.",
        min_length=1,
        max_length=10_000,
    )
    limit: int = Field(
        default=100,
        description="Maximum number of rows returned",
        ge=1,
        le=5000,
    )
    format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' for human-readable output, 'json' for programmatic use",
    )

def register_query_tools(mcp: FastMCP):

    @mcp.tool(
        name="pg_execute_query",
        annotations={
            "title": "Execute SQL Query",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def pg_execute_query(params: ExecuteQueryInput) -> str:
        """Executes a SELECT query on PostgreSQL and returns the results.

        Only read queries (SELECT) are allowed. Read-only enforcement is done
        at the database level — connect with a role that has no write privileges.

        Args:
            params.sql: Valid SELECT query
            params.limit: Row limit (default 100)
            params.format: Output format

        Returns:
            str: Results formatted as a Markdown table or JSON
        """
        # Wrap in a subquery to enforce the row cap regardless of any LIMIT
        # already present in the user's SQL.
        sql = f"SELECT * FROM ({params.sql.strip()}) AS _q LIMIT {params.limit}"

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("SET TRANSACTION READ ONLY")
                    records = await conn.fetch(sql)
        except Exception as e:
            logger.error("pg_execute_query failed: %s", e)
            raise

        data = records_to_dict(records)

        if params.format == ResponseFormat.JSON:
            return format_as_json(data)

        result = format_as_markdown_table(data)
        return f"**{len(data)} row(s) returned**\n\n{result}"
