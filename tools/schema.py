from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from core.connection import get_pool
import json

class DescribeTableInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    table_name: str = Field(..., description="Table name", min_length=1)
    schema_name: str = Field(default="public", description="PostgreSQL schema")

def register_schema_tools(mcp: FastMCP):

    @mcp.tool(
        name="pg_list_tables",
        annotations={"title": "List Tables", "readOnlyHint": True, "destructiveHint": False},
    )
    async def pg_list_tables() -> str:
        """Lists all available tables in the database, with their schemas and estimated row count."""
        sql = """
            SELECT
                table_schema,
                table_name,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_schema)||'.'||quote_ident(table_name))) AS size,
                (SELECT reltuples::bigint FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = table_name AND n.nspname = table_schema) AS row_estimate
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name;
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch(sql)

            lines = ["## Available tables\n"]
            for r in records:
                lines.append(f"- **{r['table_schema']}.{r['table_name']}** — {r['size']} (~{r['row_estimate']} rows)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing tables: {e}"

    @mcp.tool(
        name="pg_describe_table",
        annotations={"title": "Describe Table", "readOnlyHint": True, "destructiveHint": False},
    )
    async def pg_describe_table(params: DescribeTableInput) -> str:
        """Returns the full structure of a table: columns, types, constraints, and indexes."""
        sql = """
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END AS key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                  ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name = $1 AND tc.table_schema = $2
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_name = $1 AND c.table_schema = $2
            ORDER BY c.ordinal_position;
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch(sql, params.table_name, params.schema_name)

            if not records:
                return f"Table `{params.schema_name}.{params.table_name}` not found."

            lines = [f"## Structure: `{params.schema_name}.{params.table_name}`\n",
                     "| Column | Type | Nullable | Default | Key |",
                     "|--------|------|----------|---------|-----|"]
            for r in records:
                lines.append(f"| {r['column_name']} | {r['data_type']} | {r['is_nullable']} | {r['column_default'] or ''} | {r['key']} |")
            return "\n".join(lines)
        except Exception as e:
            return f"Error describing table: {e}"
