"""E-commerce analytics assistant — quickstart example.

Usage:
    export OPENAI_API_KEY=sk-...
    export DATABASE_URL=postgresql://ecommerce:ecommerce@localhost:5432/ecommerce
    python main.py
"""

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

    questions = [
        "which is the most sold product?"
    ]

    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")
        result = await pipeline.query(q)
        if result.success:
            print(result.response)
            if result.sql:
                print(f"\n[SQL]: {result.sql}")
        else:
            print(f"Error: {result.error}")

    await executor.close()


if __name__ == "__main__":
    asyncio.run(main())
