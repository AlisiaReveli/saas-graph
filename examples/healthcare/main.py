"""Healthcare analytics assistant — quickstart example.

Usage:
    export OPENAI_API_KEY=sk-...
    export DATABASE_URL=postgres://...
    python main.py
"""

import asyncio
import os

from saas_graph import NLQPipeline, DomainConfig
from saas_graph.contrib.openai import OpenAIGateway


async def main():
    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key=os.environ["OPENAI_API_KEY"]),
        domain=DomainConfig(
            name="healthcare",
            description="Hospital management system with patient, prescription, and billing data",
            schema_path="schema_context.yaml",
            column_display_names={
                "patient_id": "Patient ID",
                "admitted_at": "Admission Date",
                "discharged_at": "Discharge Date",
                "diagnosis_code": "Diagnosis (ICD-10)",
                "diagnosis_description": "Diagnosis",
                "amount": "Amount ($)",
                "insurance_covered": "Insurance Covered ($)",
                "patient_responsibility": "Patient Owes ($)",
            },
            sql_instructions=[
                "Always exclude test patients: patient_type != 'TEST'",
                "Date columns use UTC timezone",
                "Billing amounts are stored in dollars (not cents)",
            ],
        ),
    )

    questions = [
        "How many patients were admitted last month?",
        "What are the top 5 diagnoses this year?",
        "Show me all ICU patients right now",
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


if __name__ == "__main__":
    asyncio.run(main())
