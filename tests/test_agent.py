"""Regression tests for agent.py."""

import json
import subprocess
import sys
from pathlib import Path


class TestAgentOutput:
    """Test that agent.py produces valid JSON with required fields."""

    def test_agent_returns_json_with_answer_and_tool_calls(self):
        """Agent should output valid JSON with 'answer' and 'tool_calls' fields."""
        # Run agent.py with a simple question
        result = subprocess.run(
            [sys.executable, "agent.py", "What is 2+2?"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Check exit code
        assert result.returncode == 0, f"Agent failed: {result.stderr}"

        # Check stdout is not empty
        assert result.stdout.strip(), "Agent produced no output"

        # Parse JSON
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            raise AssertionError(f"Agent output is not valid JSON: {result.stdout[:200]}") from e

        # Check required fields
        assert "answer" in data, "Missing 'answer' field in output"
        assert "tool_calls" in data, "Missing 'tool_calls' field in output"

        # Check field types
        assert isinstance(data["answer"], str), "'answer' should be a string"
        assert isinstance(data["tool_calls"], list), "'tool_calls' should be an array"
