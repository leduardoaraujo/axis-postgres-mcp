import json
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from core.connection import get_pool
from core.formatters import records_to_dict, format_as_markdown_table, format_as_json
from enum import Enum

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

class ExecuteQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sql: str = Field(
        ...,
        description="SQL SELECT to execute. Read-only — INSERT/UPDATE/DELETE are blocked.",
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

        Only read queries (SELECT) are allowed.
        Use pg_list_tables and pg_describe_table to explore the schema before querying.

        Args:
            params.sql: Valid SELECT query
            params.limit: Row limit (default 100)
            params.format: Output format

        Returns:
            str: Results formatted as a Markdown table or JSON
        """
        sql = params.sql.strip()

        # Basic security — block DML/DDL
        forbidden = ("insert", "update", "delete", "drop", "create", "alter", "truncate")
        if any(sql.lower().startswith(kw) for kw in forbidden):
            return "Error: Only SELECT queries are allowed in this tool."

   
        if "limit" not in sql.lower():
            sql = f"{sql} LIMIT {params.limit}"

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch(sql)

            data = records_to_dict(records)

            if params.format == ResponseFormat.JSON:
                return format_as_json(data)

            result = format_as_markdown_table(data)
            return f"**{len(data)} row(s) returned**\n\n{result}"

        except Exception as e:
            return f"Error executing query: {e}"
