"""Inventory management assistant (MongoDB) — quickstart example.

Usage:
    export OPENAI_API_KEY=sk-...
    export MONGODB_URI=mongodb://localhost:27017
    docker compose up -d
    python main.py
"""

import asyncio
import os

from saas_graph import DomainConfig, NLQPipeline, NodeConfig
from saas_graph.contrib.mongodb import MongoDBExecutor
from saas_graph.contrib.openai import OpenAIGateway


async def main():
    executor = MongoDBExecutor(
        connection_uri=os.environ.get("MONGODB_URI", "mongodb://localhost:27018"),
        database="inventory",
    )

    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key=os.environ["OPENAI_API_KEY"]),
        executor=executor,
        node_config=NodeConfig(database_type="mongodb"),
        domain=DomainConfig(
            name="inventory",
            description="Warehouse inventory system with products, warehouses, and stock movements",
            schema_path="schema_context.yaml",
            column_display_names={
                "quantity": "Qty",
                "unit_cost": "Unit Cost ($)",
                "total_value": "Total Value ($)",
                "capacity": "Capacity (units)",
            },
            sql_instructions=[
                "Stock movements have type: 'inbound', 'outbound', or 'transfer'",
                "Current stock per product per warehouse is in the stock collection",
                "Use ISODate-compatible strings for date comparisons",
            ],
        ),
    )

    questions = [
        "Which warehouse has the most total stock?",
        "What are the top 5 products by total inventory value?",
        "Show me all outbound movements from last month",
    ]

    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")
        result = await pipeline.query(q)
        if result.success:
            print(result.response)
            if result.sql:
                print(f"\n[Query]: {result.sql}")
        else:
            print(f"Error: {result.error}")

    await executor.close()


if __name__ == "__main__":
    asyncio.run(main())
