"""Tests for OpenAIGateway helper methods."""

import json

import pytest

from saas_graph.contrib.openai import OpenAIGateway


class TestStripCodeFence:
    def test_json_fence(self):
        raw = '```json\n{"sql": "SELECT 1", "explanation": "test"}\n```'
        result = OpenAIGateway._strip_code_fence(raw)
        parsed = json.loads(result)
        assert parsed["sql"] == "SELECT 1"

    def test_plain_fence(self):
        raw = '```\n{"sql": "SELECT 1"}\n```'
        result = OpenAIGateway._strip_code_fence(raw)
        parsed = json.loads(result)
        assert parsed["sql"] == "SELECT 1"

    def test_no_fence(self):
        raw = '{"sql": "SELECT 1"}'
        result = OpenAIGateway._strip_code_fence(raw)
        assert result == raw

    def test_whitespace(self):
        raw = '  ```json\n{"sql": "SELECT 1"}\n```  '
        result = OpenAIGateway._strip_code_fence(raw)
        parsed = json.loads(result)
        assert parsed["sql"] == "SELECT 1"


class TestExtractSqlFromText:
    def test_sql_fence(self):
        text = "Here's the query:\n```sql\nSELECT * FROM users\n```"
        result = OpenAIGateway._extract_sql_from_text(text)
        assert result == "SELECT * FROM users"

    def test_json_fence_with_sql_key(self):
        data = {"sql": "SELECT count(*) FROM orders", "explanation": "counts orders"}
        text = f"```json\n{json.dumps(data)}\n```"
        result = OpenAIGateway._extract_sql_from_text(text)
        assert result == "SELECT count(*) FROM orders"

    def test_plain_text(self):
        text = "SELECT 1"
        result = OpenAIGateway._extract_sql_from_text(text)
        assert result == "SELECT 1"

    def test_generic_fence(self):
        text = "```\nSELECT * FROM products\n```"
        result = OpenAIGateway._extract_sql_from_text(text)
        assert result == "SELECT * FROM products"
