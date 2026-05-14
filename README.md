## Demo
<video src="demo.mp4" controls width="600"></video>


# saas-graph

**Connect your database. Get an AI analyst. Ship in a day.**

A Python framework for SaaS companies that want to add a natural-language analytics assistant to their product. You provide your database connection and a schema description — saas-graph handles query understanding, schema-aware retrieval, SQL generation with retry loops, result formatting, and real-time streaming.

## Quick Start

```bash
pip install saas-graph[openai,postgres,server]
```

### 1. Start a database

```bash
cd examples/ecommerce
docker compose up -d
```

This starts a local PostgreSQL with sample e-commerce data: 50 products, 200 customers, 500 orders, and ~1,500 order items.

### 2. Set your environment

```bash
export OPENAI_API_KEY=sk-...
export DATABASE_URL=postgresql://ecommerce:ecommerce@localhost:5432/ecommerce
```

### 3. Run the example

```python
import asyncio
import os

from saas_graph import NLQPipeline, DomainConfig
from saas_graph.contrib.openai import OpenAIGateway
from saas_graph.contrib.postgres import PostgresExecutor


async def main():
    executor = PostgresExecutor(os.environ["DATABASE_URL"])

    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key=os.environ["OPENAI_API_KEY"]),
        executor=executor,
        domain=DomainConfig(
            name="ecommerce",
            description="E-commerce platform with products, orders, and customers",
            schema_path="schema_context.yaml",
            column_display_names={
                "total_amount": "Total ($)",
                "line_total": "Line Total ($)",
                "price": "Price ($)",
                "revenue": "Revenue ($)",
                "lifetime_value": "LTV ($)",
            },
        ),
    )

    result = await pipeline.query("What are my top 10 products by revenue this quarter?")
    print(result.response)
    print(result.sql)

    await executor.close()

asyncio.run(main())
```

Or run the example directly:

```bash
cd examples/ecommerce
python main.py
```

### Example output

```
| Rank | Product Name                 | Total Revenue |
|------|------------------------------|---------------|
| 1    | 27" 4K Monitor               | $4,949.89     |
| 2    | Adjustable Dumbbell Pair     | $2,999.80     |
| 3    | Running Sneakers             | $2,759.77     |
| 4    | Noise Cancelling Earbuds     | $2,549.83     |
| 5    | Smart Watch Fitness Tracker  | $2,199.89     |
| ...  | ...                          | ...           |
```

### 4. FastAPI server

```python
from fastapi import FastAPI
from saas_graph import NLQPipeline, DomainConfig
from saas_graph.contrib.openai import OpenAIGateway
from saas_graph.contrib.postgres import PostgresExecutor
from saas_graph.server import create_router

app = FastAPI()
pipeline = NLQPipeline(
    llm=OpenAIGateway(api_key="sk-..."),
    executor=PostgresExecutor("postgresql://ecommerce:ecommerce@localhost:5432/ecommerce"),
    domain=DomainConfig(
        name="ecommerce",
        schema_path="schema_context.yaml",
    ),
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

## Schema Context

Describe your database in `schema_context.yaml`:

```yaml
tables:
  products:
    description: "Product catalog"
    columns:
      product_id: { type: integer, description: "Unique product ID" }
      name: { type: text, description: "Product name" }
      category: { type: text, description: "Product category" }
      price: { type: numeric, description: "Current price in dollars" }

  orders:
    description: "Customer orders"
    columns:
      order_id: { type: integer, description: "Unique order ID" }
      customer_id: { type: integer, description: "FK to customers" }
      order_date: { type: timestamp, description: "When the order was placed" }
      status: { type: text, description: "pending, shipped, delivered, returned" }
      total_amount: { type: numeric, description: "Order total in dollars" }
    joins:
      - { to: customers, on: "customer_id = customer_id", type: LEFT }

business_rules:
  - name: exclude_cancelled
    trigger_terms: [orders, revenue, sales]
    sql_condition: "status != 'cancelled'"
    description: "Exclude cancelled orders from revenue/sales metrics by default"

golden_queries:
  - name: top_products_by_revenue
    question: "What are the top selling products by revenue?"
    sql: |
      SELECT p.name, SUM(oi.line_total) as revenue
      FROM order_items oi
      JOIN products p ON oi.product_id = p.product_id
      JOIN orders o ON oi.order_id = o.order_id
      WHERE o.status != 'cancelled'
      GROUP BY p.name
      ORDER BY revenue DESC
      LIMIT 10
    tables: [order_items, products, orders]
```

Auto-generate the initial YAML from any PostgreSQL database:

```bash
saas-graph scan postgres://user:pass@host/db
```

## Swappable Components

Every infrastructure component is behind an abstract interface:

| Component | Interface | Built-in Adapters |
|-----------|-----------|-------------------|
| LLM | `ILLMGateway` | `OpenAIGateway` |
| Database | `IQueryExecutor` | `PostgresExecutor` |
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
pip install saas-graph[openai,postgres,server]

# Everything
pip install saas-graph[all]
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
