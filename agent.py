#!/usr/bin/env python3
"""CLI agent that calls an LLM with tools and returns a structured JSON answer.

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output:
    {"answer": "...", "source": "...", "tool_calls": [...]}
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_TOOL_CALLS = 10
PROJECT_ROOT = Path(__file__).parent.resolve()


# ---------------------------------------------------------------------------
# Environment Loading
# ---------------------------------------------------------------------------

def load_env():
    """Load environment variables from .env.agent.secret and .env.docker.secret.

    .env.agent.secret contains LLM configuration (LLM_API_KEY, LLM_API_BASE, LLM_MODEL).
    .env.docker.secret contains backend API configuration (LMS_API_KEY).

    Both files are optional - if missing, the agent relies on environment variables
    (useful for autochecker evaluation).
    """
    # Load LLM configuration from .env.agent.secret
    agent_env_file = Path(".env.agent.secret")
    if agent_env_file.exists():
        for line in agent_env_file.read_text().splitlines():
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

    # Load backend API configuration from .env.docker.secret
    docker_env_file = Path(".env.docker.secret")
    if docker_env_file.exists():
        for line in docker_env_file.read_text().splitlines():
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


# Load environment variables at module import time
load_env()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def validate_path(path: str) -> tuple[bool, str]:
    """Validate that path doesn't traverse outside project directory.

    Returns:
        (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"

    if ".." in path:
        return False, "Path traversal not allowed"

    if path.startswith("/"):
        return False, "Path must be relative"

    full_path = PROJECT_ROOT / path
    try:
        full_path.resolve().relative_to(PROJECT_ROOT)
        return True, ""
    except ValueError:
        return False, "Path must be within project directory"


def read_file(path: str) -> str:
    """Read contents of a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    file_path = PROJECT_ROOT / path

    if not file_path.exists():
        return f"Error: File not found: {path}"

    if not file_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated list of entries, or error message
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    dir_path = PROJECT_ROOT / path

    if not dir_path.exists():
        return f"Error: Path not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted([e.name for e in dir_path.iterdir()])
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method: str, path: str, body: str = None) -> str:
    """Call the backend LMS API with authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API endpoint path (e.g., '/items/', '/analytics')
        body: Optional JSON request body for POST/PUT requests

    Returns:
        JSON string with status_code and body, or error message
    """
    import urllib.request
    import urllib.error

    api_base = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    lms_api_key = os.environ.get("LMS_API_KEY", "")

    url = f"{api_base}{path}"

    headers = {
        "Content-Type": "application/json",
    }

    if lms_api_key:
        headers["Authorization"] = f"Bearer {lms_api_key}"

    data = None
    if body:
        try:
            data = json.dumps(json.loads(body)).encode("utf-8")
        except json.JSONDecodeError:
            return json.dumps({"status_code": 0, "body": "Invalid JSON body"})

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            try:
                parsed_body = json.loads(response_body)
            except json.JSONDecodeError:
                parsed_body = response_body
            result = {
                "status_code": response.status,
                "body": parsed_body
            }
            return json.dumps(result)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            parsed_body = json.loads(error_body)
        except json.JSONDecodeError:
            parsed_body = error_body
        result = {
            "status_code": e.code,
            "body": parsed_body
        }
        return json.dumps(result)
    except urllib.error.URLError as e:
        return json.dumps({"status_code": 0, "body": f"Connection error: {e.reason}"})
    except Exception as e:
        return json.dumps({"status_code": 0, "body": f"Error: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool Schemas for LLM
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read documentation, code files, or configuration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path in the project repository. Use this to discover what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend LMS API to query data, check status codes, or test endpoints. Use this for data-dependent questions (item counts, scores, analytics) or to check HTTP responses. Requires authentication via LMS_API_KEY.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

TOOLS_MAP = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
}


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a documentation and system assistant for a software engineering project.

Your task is to answer questions about the project by:
- Reading documentation files in the wiki directory
- Reading source code to understand system architecture
- Querying the backend API for data-dependent questions

Available tools:
- list_files: List files in a directory (use to discover wiki or source files)
- read_file: Read contents of a file (use for wiki docs, source code, configuration)
- query_api: Call the backend LMS API (use for data queries, status codes, analytics)

Strategy:
1. For wiki/documentation questions (e.g., "According to the wiki...") → use list_files and read_file on wiki/*.md
2. For system facts (e.g., "What framework...", "What port...") → use read_file on source code files
3. For data queries (e.g., "How many items...", "What status code...", "Query /analytics...") → use query_api
4. For bug diagnosis → use query_api to reproduce the error, then read_file to find the bug in source code

Rules:
- Always include the source field in your final answer when reading files
- Make tool calls one at a time, not all at once
- If you find the answer, provide it with the source reference
- If you cannot find the answer after reading relevant files, say so
- For API queries, include the endpoint path and status code in your answer

Respond with tool calls when you need information, or with a final answer when you have enough information."""


# ---------------------------------------------------------------------------
# LLM API
# ---------------------------------------------------------------------------

def call_llm(messages: list[dict], timeout: int = 60) -> dict:
    """Call the LLM API and return the response.

    Args:
        messages: List of message dicts with role and content
        timeout: Request timeout in seconds

    Returns:
        Parsed LLM response dict
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
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "tool_choice": "auto"
    }

    data = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach LLM API: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM response: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Agentic Loop
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments

    Returns:
        Tool result as string
    """
    if tool_name not in TOOLS_MAP:
        return f"Error: Unknown tool: {tool_name}"

    func = TOOLS_MAP[tool_name]
    try:
        return func(**args)
    except Exception as e:
        return f"Error executing tool: {e}"


def run_agent(question: str, timeout: int = 60) -> dict:
    """Run the agentic loop and return the final response.

    Args:
        question: User's question
        timeout: Total timeout in seconds

    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    # Initialize conversation with system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    # Track all tool calls for output
    all_tool_calls = []

    # Agentic loop
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        # Call LLM
        response = call_llm(messages, timeout=timeout)

        # Check for tool calls
        choices = response.get("choices", [])
        if not choices:
            return {
                "answer": "Error: No response from LLM",
                "source": "",
                "tool_calls": all_tool_calls
            }

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])

        # If no tool calls, we have the final answer
        if not tool_calls:
            content = message.get("content", "")
            # Try to extract source from the answer
            source = extract_source(content)
            return {
                "answer": content,
                "source": source,
                "tool_calls": all_tool_calls
            }

        # Execute tool calls
        for tool_call in tool_calls:
            tool_call_count += 1
            if tool_call_count > MAX_TOOL_CALLS:
                break

            # Parse tool call
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            args_str = function.get("arguments", "{}")

            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            # Execute tool
            result = execute_tool(tool_name, args)

            # Record tool call
            all_tool_calls.append({
                "tool": tool_name,
                "args": args,
                "result": result
            })

            # Add tool result to messages
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [tool_call]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", f"call_{tool_call_count}"),
                "content": result
            })

    # Max tool calls reached
    return {
        "answer": "Maximum tool calls reached. Here's what I found so far.",
        "source": extract_source(all_tool_calls[-1]["result"]) if all_tool_calls else "",
        "tool_calls": all_tool_calls
    }


def extract_source(content: str) -> str:
    """Try to extract a source reference from the answer content.

    Looks for patterns like wiki/file.md or wiki/file.md#section
    """
    import re

    # Look for wiki file references
    pattern = r'(wiki/[\w\-/]+\.[\w]+(?:#[\w\-]+)?)'
    match = re.search(pattern, content)

    if match:
        return match.group(1)

    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Run agent and get response
    response = run_agent(question)

    # Output JSON to stdout
    print(json.dumps(response))


if __name__ == "__main__":
    main()
