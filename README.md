# saas-graph

**Connect your database. Get an AI analyst. Ship in a day.**

A Python framework for SaaS companies that want to add a natural-language analytics assistant to their product. You provide your database connection and a schema description — saas-graph handles query understanding, schema-aware retrieval, SQL generation with retry loops, result formatting, and real-time streaming.

## Quick Start

```bash
pip install saas-graph[openai,postgres,server]
```

### Option 1: CLI (fastest)

```bash
# Scaffold a project
saas-graph init my-analytics

# Auto-discover your database schema
saas-graph scan postgres://user:pass@localhost/mydb

# Start the server
export OPENAI_API_KEY=sk-...
saas-graph serve
```

### Option 2: Python API

```python
import asyncio
from saas_graph import NLQPipeline, DomainConfig
from saas_graph.contrib.openai import OpenAIGateway

async def main():
    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key="sk-..."),
        domain=DomainConfig(
            name="healthcare",
            schema_path="schema_context.yaml",
        ),
    )

    result = await pipeline.query("How many patients were admitted last month?")
    print(result.response)
    print(result.sql)

asyncio.run(main())
```

### Option 3: FastAPI Plugin

```python
from fastapi import FastAPI
from saas_graph import NLQPipeline, DomainConfig
from saas_graph.contrib.openai import OpenAIGateway
from saas_graph.server import create_router

app = FastAPI()
pipeline = NLQPipeline(
    llm=OpenAIGateway(api_key="sk-..."),
    domain=DomainConfig(schema_path="schema_context.yaml"),
)
app.include_router(create_router(pipeline), prefix="/api")
```

This gives you:
- `POST /api/chat` — non-streaming query
- `POST /api/chat/stream` — SSE streaming with thinking events

## Architecture

```
User Question
    │
    ▼
┌──────────┐     ┌───────────┐     ┌──────────────┐
│ Clarifier │────▶│  Router   │────▶│ Schema Linker│
│ (optional)│     │int / ext  │     │ semantic RAG │
└──────────┘     └───────────┘     └──────────────┘
                      │ external          │
                      ▼                   ▼
                 ┌──────────┐     ┌──────────────┐
                 │Web Search│     │   Planner    │
                 └──────────┘     │  (optional)  │
                      │           └──────────────┘
                      │                   │
                      │                   ▼
                      │           ┌──────────────┐
                      │           │SQL Generator │◀─── retry with
                      │           │  (LLM-based) │     error feedback
                      │           └──────────────┘
                      │                   │
                      │                   ▼
                      │           ┌──────────────┐
                      │           │  Executor    │
                      │           │  (database)  │
                      │           └──────────────┘
                      │                   │
                      ▼                   ▼
                 ┌─────────────────────────────┐
                 │         Formatter            │
                 │  (LLM markdown formatting)   │
                 └─────────────────────────────┘
                              │
                              ▼
                      Formatted Response
```

Each node is a standalone async callable. The pipeline runs as a [LangGraph](https://github.com/langchain-ai/langgraph) state graph — or falls back to a pure-Python executor when LangGraph isn't installed.

## What Makes This Different

| Feature | Vanna.ai | Wren AI | **saas-graph** |
|---------|----------|---------|----------------|
| Multi-tenant isolation | No | No | **Yes** |
| Clarification loop | No | No | **Yes** |
| Golden query cache | Train on pairs | No | **Hybrid vector+keyword** |
| Retry with error feedback | No | No | **Up to 5 retries** |
| Schema-aware RAG | Basic | Semantic layer | **Embedding search on tables, columns, joins, rules** |
| Streaming thinking UX | No | No | **SSE events per stage** |
| Business rules injection | No | No | **YAML-defined** |
| Drop-in FastAPI server | No | Docker only | **`create_router()` or CLI** |

## Schema Context

Describe your database in `schema_context.yaml`:

```yaml
tables:
  patients:
    description: "Patient records"
    columns:
      patient_id: { type: int, description: "Unique ID" }
      name: { type: text, description: "Full name" }
      ward: { type: text, description: "Ward (A, B, ICU, ER)" }
      admitted_at: { type: timestamp, description: "Admission date" }
    aliases:
      - { name: "ICU patients", filter: "ward = 'ICU'" }
    joins:
      - { to: prescriptions, on: "patient_id = patient_id", type: LEFT }

business_rules:
  - name: exclude_test
    trigger_terms: [patients]
    sql_condition: "patient_type != 'TEST'"
    description: "Exclude test records"

golden_queries:
  - name: monthly_admissions
    question: "How many patients were admitted last month?"
    sql: "SELECT COUNT(*) FROM patients WHERE ..."
    tables: [patients]
```

Auto-generate the initial YAML from any PostgreSQL database:

```bash
saas-graph scan postgres://user:pass@host/db
```

## Domain Configuration

Customize the pipeline for your domain without writing node code:

```python
DomainConfig(
    name="healthcare",
    description="Hospital management system",
    schema_path="schema_context.yaml",
    column_display_names={
        "patient_id": "Patient ID",
        "admitted_at": "Admission Date",
        "amount": "Amount ($)",
    },
    clarification_prompt="You are a healthcare analytics assistant...",
    sql_instructions=[
        "Always exclude test patients",
        "Dates are in UTC",
    ],
    tenant_id_column="hospital_id",
)
```

## Swappable Components

Every infrastructure component is behind an abstract interface:

| Component | Interface | Built-in Adapters |
|-----------|-----------|-------------------|
| LLM | `ILLMGateway` | `OpenAIGateway` |
| Database | `IQueryExecutor` | (bring your own) |
| Embeddings | `IEmbeddingService` | (bring your own) |
| Schema | `ISchemaContextLoader` | `YAMLSchemaLoader` |
| Knowledge | `IKnowledgeRepository` | (bring your own) |
| Cache | `ICacheStore` | `InMemoryCache` |
| Sessions | `ISessionStore` | `InMemorySessionStore` |
| Web Search | `IWebSearchService` | (bring your own) |

## Installation

```bash
# Minimal (just the framework)
pip install saas-graph

# With OpenAI + PostgreSQL
pip install saas-graph[openai,postgres]

# With FastAPI server
pip install saas-graph[openai,server]

# Everything
pip install saas-graph[all]
```

## Examples

- [`examples/healthcare/`](examples/healthcare/) — Hospital analytics assistant
- [`examples/ecommerce/`](examples/ecommerce/) — E-commerce analytics assistant

## License

Apache 2.0 — see [LICENSE](LICENSE).
