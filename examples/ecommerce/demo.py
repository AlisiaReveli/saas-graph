"""Streamlit demo — saas-graph e-commerce analytics chat."""

import asyncio
import os

import streamlit as st

from saas_graph import DomainConfig, NLQPipeline
from saas_graph.contrib.openai import OpenAIGateway
from saas_graph.contrib.postgres import PostgresExecutor

st.set_page_config(page_title="saas-graph demo", page_icon="📊", layout="wide")

SUGGESTED = [
    "Top 10 products by revenue",
    "Orders placed last month",
    "Revenue by category",
    "Top customers by LTV",
    "Average order value",
]

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://ecommerce:ecommerce@localhost:5432/ecommerce",
)


def get_pipeline(api_key: str):
    return NLQPipeline(
        llm=OpenAIGateway(api_key=api_key),
        executor=PostgresExecutor(DATABASE_URL),
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


def run_query(api_key: str, question: str):
    pipeline = get_pipeline(api_key)
    return asyncio.run(pipeline.query(question))


# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        value=os.environ.get("OPENAI_API_KEY", ""),
    )
    if not api_key:
        st.warning("Enter your OpenAI API key to start.")

    st.divider()
    st.caption("**Database:** ecommerce @ localhost:5432")
    st.caption("50 products · 200 customers · 500 orders")
    st.divider()
    st.caption("[saas-graph on GitHub](https://github.com/AlisiaReveli/saas-graph)")

# --- Main ---
st.title("📊 saas-graph demo")
st.caption("Ask anything about the e-commerce database — products, orders, customers, revenue.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

cols = st.columns(len(SUGGESTED))
for i, q in enumerate(SUGGESTED):
    if cols[i].button(q, key=f"sug_{i}", use_container_width=True):
        st.session_state.pending = q

prompt = st.chat_input("Ask a question about your data...")
if "pending" in st.session_state:
    prompt = st.session_state.pop("pending")

if prompt:
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = run_query(api_key, prompt)

        if result.success:
            st.markdown(result.response)
            if result.sql:
                with st.expander("🔍 View SQL"):
                    st.code(result.sql, language="sql")
        else:
            st.error(result.error or "Something went wrong.")

        reply = result.response if result.success else (result.error or "Error")
        st.session_state.messages.append({"role": "assistant", "content": reply})
