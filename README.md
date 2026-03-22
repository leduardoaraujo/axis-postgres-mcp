# axis-postgres-mcp

PostgreSQL MCP server. Exposes read-only data access and schema inspection as tools for Claude.

## Tools

- `pg_execute_query` — runs a SELECT and returns the results
- `pg_list_tables` — lists all tables with size and row estimates
- `pg_describe_table` — shows the columns of a table

## Configuration

Create a `.env` file at the project root:

```env
POSTGRES_DSN=postgresql://user:password@localhost:5432/mydb
```

## Installation

```bash
pip install asyncpg pydantic python-dotenv mcp
```

## Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "python",
      "args": ["/path/to/axis-postgres-mcp/server.py"],
      "env": {
        "POSTGRES_DSN": "postgresql://user:password@localhost:5432/mydb"
      }
    }
  }
}
```

## Security

All queries run inside a read-only transaction. Recommended to connect with a role that only has `SELECT`:

```sql
CREATE ROLE mcp_reader WITH LOGIN PASSWORD 'secret';
GRANT CONNECT ON DATABASE mydb TO mcp_reader;
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_reader;
```
