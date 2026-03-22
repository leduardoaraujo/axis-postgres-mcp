# axis-postgres-mcp

PostgreSQL MCP server. Exposes read-only data access and schema inspection as tools for Claude.

## Tools

- `pg_execute_query` — runs a SELECT and returns results (markdown or JSON)
- `pg_list_tables` — lists tables with size and row estimates (optional schema filter)
- `pg_describe_table` — shows columns, foreign keys, and indexes of a table

## Configuration

Create a `.env` file at the project root:

```env
POSTGRES_DSN=postgresql://user:password@localhost:5432/mydb
```

## Installation

```bash
pip install -r requirements.txt
```

## Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "python",
      "args": ["C:/path/to/axis-postgres-mcp/server.py"],
      "env": {
        "POSTGRES_DSN": "postgresql://user:password@host:5432/mydb"
      }
    }
  }
}
```

## Security

All queries run inside a read-only transaction (`SET TRANSACTION READ ONLY`).
Recommended to connect with a role that only has `SELECT`:

```sql
CREATE ROLE mcp_reader WITH LOGIN PASSWORD 'secret';
GRANT CONNECT ON DATABASE mydb TO mcp_reader;
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_reader;
```

## Logging

Logs are written to **stderr** (visible in Claude Desktop's MCP log panel) and include
startup/shutdown events and connection pool lifecycle.
