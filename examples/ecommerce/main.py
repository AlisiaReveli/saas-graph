"""E-commerce analytics assistant — quickstart example."""

import asyncio
import os

from saas_graph import NLQPipeline, DomainConfig
from saas_graph.contrib.openai import OpenAIGateway


async def main():
    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key=os.environ["OPENAI_API_KEY"]),
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


if __name__ == "__main__":
    asyncio.run(main())
