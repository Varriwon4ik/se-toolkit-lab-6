#!/usr/bin/env python3
"""CLI agent that calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {"answer": "...", "tool_calls": []}
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def load_env():
    """Load environment variables from .env.agent.secret."""
    env_file = Path(".env.agent.secret")
    if not env_file.exists():
        print("Error: .env.agent.secret not found", file=sys.stderr)
        sys.exit(1)

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def call_llm(question: str, timeout: int = 60) -> dict:
    """Call the LLM API and return the response.

    Args:
        question: The user's question
        timeout: Request timeout in seconds

    Returns:
        dict with 'answer' and 'tool_calls' fields
    """
    api_base = os.environ.get("LLM_API_BASE", "")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "qwen3-coder-plus")

    if not api_base:
        print("Error: LLM_API_BASE not set", file=sys.stderr)
        sys.exit(1)

    url = f"{api_base}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": question}
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    # Add authorization header if API key is provided
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return {
                "answer": content,
                "tool_calls": []
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach LLM API: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Failed to parse LLM response: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load environment configuration
    load_env()

    # Call LLM and get response
    response = call_llm(question)

    # Output JSON to stdout
    print(json.dumps(response))


if __name__ == "__main__":
    main()
