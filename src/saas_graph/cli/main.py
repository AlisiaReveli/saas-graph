"""saas-graph CLI: init, scan, serve, test."""

from __future__ import annotations

import sys


def _ensure_typer():
    try:
        import typer  # noqa: F401
    except ImportError:
        print("CLI requires: pip install saas-graph[cli]", file=sys.stderr)
        sys.exit(1)


_ensure_typer()

import typer
from rich.console import Console

app = typer.Typer(
    name="saas-graph",
    help="AI analytics assistant framework — connect your database, get natural language querying.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init(name: str = typer.Argument("my-analytics", help="Project directory name")):
    """Scaffold a new saas-graph project."""
    from pathlib import Path

    project_dir = Path(name)
    project_dir.mkdir(parents=True, exist_ok=True)

    schema_file = project_dir / "schema_context.yaml"
    if not schema_file.exists():
        schema_file.write_text(
            "# saas-graph schema context\n"
            "# Run `saas-graph scan <database_url>` to auto-populate.\n\n"
            "tables:\n"
            "  # example_table:\n"
            '  #   description: "Description of the table"\n'
            "  #   columns:\n"
            '  #     id: { type: int, description: "Primary key" }\n'
            "  #   joins:\n"
            '  #     - { to: other_table, on: "id = other_id", type: LEFT }\n\n'
            "business_rules: []\n\n"
            "golden_queries: []\n"
        )

    env_file = project_dir / ".env.example"
    if not env_file.exists():
        env_file.write_text(
            "OPENAI_API_KEY=sk-...\n"
            "DATABASE_URL=postgres://user:pass@localhost:5432/mydb\n"
        )

    main_file = project_dir / "main.py"
    if not main_file.exists():
        main_file.write_text(
            '"""Quick-start: run with `python main.py`"""\n\n'
            "import asyncio\n"
            "import os\n\n"
            "from saas_graph import NLQPipeline, DomainConfig\n"
            "from saas_graph.contrib.openai import OpenAIGateway\n\n\n"
            "async def main():\n"
            '    pipeline = NLQPipeline(\n'
            '        llm=OpenAIGateway(api_key=os.environ["OPENAI_API_KEY"]),\n'
            '        domain=DomainConfig(\n'
            '            name="my-analytics",\n'
            '            schema_path="schema_context.yaml",\n'
            "        ),\n"
            "    )\n"
            '    result = await pipeline.query("Show me the top 10 records")\n'
            "    print(result.response)\n\n\n"
            'if __name__ == "__main__":\n'
            "    asyncio.run(main())\n"
        )

    console.print(f"[green]Project initialized at ./{name}/[/green]")
    console.print(f"  [dim]schema_context.yaml[/dim]  — describe your database schema")
    console.print(f"  [dim].env.example[/dim]         — configuration template")
    console.print(f"  [dim]main.py[/dim]              — quick-start script")
    console.print(f"\nNext: [bold]cd {name} && saas-graph scan <database_url>[/bold]")


@app.command()
def scan(
    database_url: str = typer.Argument(..., help="PostgreSQL connection string"),
    output: str = typer.Option("schema_context.yaml", "--output", "-o"),
):
    """Auto-discover database schema and write schema_context.yaml."""
    import asyncio

    async def _scan():
        try:
            import asyncpg
        except ImportError:
            console.print("[red]Requires: pip install saas-graph[postgres][/red]")
            raise typer.Exit(1)

        console.print(f"Connecting to database...")
        conn = await asyncpg.connect(database_url)

        try:
            rows = await conn.fetch(
                """
                SELECT table_name, column_name, data_type, is_nullable,
                       col_description((table_schema||'.'||table_name)::regclass, ordinal_position) as description
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
                """
            )

            tables: dict = {}
            for row in rows:
                tn = row["table_name"]
                if tn not in tables:
                    tables[tn] = {"description": "", "columns": {}}
                col_info = {"type": row["data_type"]}
                if row["description"]:
                    col_info["description"] = row["description"]
                tables[tn]["columns"][row["column_name"]] = col_info

            fk_rows = await conn.fetch(
                """
                SELECT
                    tc.table_name as from_table,
                    kcu.column_name as from_column,
                    ccu.table_name as to_table,
                    ccu.column_name as to_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
                """
            )

            for fk in fk_rows:
                ft = fk["from_table"]
                if ft in tables:
                    if "joins" not in tables[ft]:
                        tables[ft]["joins"] = []
                    tables[ft]["joins"].append({
                        "to": fk["to_table"],
                        "on": f"{fk['from_column']} = {fk['to_column']}",
                        "type": "LEFT",
                    })

            import yaml
            from pathlib import Path

            output_data = {
                "tables": tables,
                "business_rules": [],
                "golden_queries": [],
            }

            Path(output).write_text(yaml.dump(output_data, default_flow_style=False, sort_keys=False))
            console.print(f"[green]Discovered {len(tables)} tables → {output}[/green]")
            console.print("Next: edit the file to add descriptions, aliases, and business rules.")

        finally:
            await conn.close()

    asyncio.run(_scan())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port", "-p"),
    schema: str = typer.Option("schema_context.yaml", "--schema", "-s"),
):
    """Start a FastAPI development server with chat endpoints."""
    import os

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]Set OPENAI_API_KEY environment variable[/red]")
        raise typer.Exit(1)

    try:
        from fastapi import FastAPI
        import uvicorn
    except ImportError:
        console.print("[red]Requires: pip install saas-graph[server][/red]")
        raise typer.Exit(1)

    from saas_graph import NLQPipeline, DomainConfig
    from saas_graph.contrib.openai import OpenAIGateway
    from saas_graph.server import create_router

    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key=api_key),
        domain=DomainConfig(schema_path=schema),
    )

    fastapi_app = FastAPI(title="saas-graph", version="0.1.0")
    fastapi_app.include_router(create_router(pipeline), prefix="/api")

    console.print(f"[green]Starting server at http://{host}:{port}[/green]")
    console.print(f"  POST /api/chat        — non-streaming query")
    console.print(f"  POST /api/chat/stream  — SSE streaming query")
    console.print(f"  Docs: http://{host}:{port}/docs")

    uvicorn.run(fastapi_app, host=host, port=port)


@app.command()
def test(
    golden: str = typer.Argument("golden_queries.yaml", help="Path to golden queries YAML"),
    schema: str = typer.Option("schema_context.yaml", "--schema", "-s"),
):
    """Test pipeline accuracy against golden queries."""
    console.print(f"[dim]Testing against {golden}...[/dim]")
    console.print("[yellow]Test runner coming soon.[/yellow]")


if __name__ == "__main__":
    app()
