import logging
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from core.connection import get_pool

logger = logging.getLogger(__name__)


class ListTablesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_name: Optional[str] = Field(
        default=None,
        description="Filter by PostgreSQL schema (e.g. 'public'). If omitted, lists all schemas.",
    )


class DescribeTableInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    table_name: str = Field(..., description="Table name", min_length=1)
    schema_name: str = Field(default="public", description="PostgreSQL schema")


def register_schema_tools(mcp: FastMCP):

    @mcp.tool(
        name="pg_list_tables",
        annotations={"title": "List Tables", "readOnlyHint": True, "destructiveHint": False},
    )
    async def pg_list_tables(params: ListTablesInput) -> str:
        """Lists available tables in the database, with their schemas and estimated row count.

        Args:
            params.schema_name: Optional schema filter (e.g. 'public')

        Returns:
            str: Markdown-formatted list of tables
        """
        sql = """
            SELECT
                table_schema,
                table_name,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_schema)||'.'||quote_ident(table_name))) AS size,
                (SELECT reltuples::bigint FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE c.relname = t.table_name AND n.nspname = t.table_schema) AS row_estimate
            FROM information_schema.tables t
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
              AND ($1::text IS NULL OR table_schema = $1)
            ORDER BY table_schema, table_name;
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch(sql, params.schema_name)
        except Exception as e:
            logger.error("pg_list_tables failed: %s", e)
            raise

        lines = ["## Available tables\n"]
        for r in records:
            lines.append(f"- **{r['table_schema']}.{r['table_name']}** — {r['size']} (~{r['row_estimate']} rows)")
        return "\n".join(lines)

    @mcp.tool(
        name="pg_describe_table",
        annotations={"title": "Describe Table", "readOnlyHint": True, "destructiveHint": False},
    )
    async def pg_describe_table(params: DescribeTableInput) -> str:
        """Returns the full structure of a table: columns, types, constraints, foreign keys, and indexes.

        Args:
            params.table_name: Name of the table
            params.schema_name: PostgreSQL schema (default 'public')

        Returns:
            str: Markdown-formatted table structure
        """
        columns_sql = """
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

        fk_sql = """
            SELECT
                ku.column_name,
                ccu.table_schema AS ref_schema,
                ccu.table_name   AS ref_table,
                ccu.column_name  AS ref_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
              ON tc.constraint_name = ku.constraint_name AND tc.table_schema = ku.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = $1 AND tc.table_schema = $2
            ORDER BY ku.column_name;
        """

        indexes_sql = """
            SELECT
                i.relname AS index_name,
                am.amname AS index_type,
                array_agg(a.attname ORDER BY x.ordinality) AS columns,
                ix.indisunique AS is_unique,
                ix.indisprimary AS is_primary
            FROM pg_index ix
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_am am ON am.oid = i.relam
            JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, ordinality) ON TRUE
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
            WHERE t.relname = $1 AND n.nspname = $2
            GROUP BY i.relname, am.amname, ix.indisunique, ix.indisprimary
            ORDER BY i.relname;
        """

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                columns = await conn.fetch(columns_sql, params.table_name, params.schema_name)
                fks = await conn.fetch(fk_sql, params.table_name, params.schema_name)
                indexes = await conn.fetch(indexes_sql, params.table_name, params.schema_name)
        except Exception as e:
            logger.error("pg_describe_table failed: %s", e)
            raise

        if not columns:
            return f"Table `{params.schema_name}.{params.table_name}` not found."

        lines = [
            f"## Structure: `{params.schema_name}.{params.table_name}`\n",
            "| Column | Type | Nullable | Default | Key |",
            "|--------|------|----------|---------|-----|",
        ]
        for r in columns:
            lines.append(
                f"| {r['column_name']} | {r['data_type']} | {r['is_nullable']} "
                f"| {r['column_default'] or ''} | {r['key']} |"
            )

        if fks:
            lines.append("\n### Foreign Keys\n")
            for fk in fks:
                lines.append(
                    f"- `{fk['column_name']}` → "
                    f"`{fk['ref_schema']}.{fk['ref_table']}.{fk['ref_column']}`"
                )

        if indexes:
            lines.append("\n### Indexes\n")
            for idx in indexes:
                cols = ", ".join(idx["columns"])
                flags = []
                if idx["is_primary"]:
                    flags.append("PRIMARY")
                elif idx["is_unique"]:
                    flags.append("UNIQUE")
                flag_str = f" ({', '.join(flags)})" if flags else ""
                lines.append(f"- **{idx['index_name']}** [{idx['index_type']}] on ({cols}){flag_str}")

        return "\n".join(lines)
