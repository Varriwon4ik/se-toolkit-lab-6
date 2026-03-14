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
    }
]

TOOLS_MAP = {
    "read_file": read_file,
    "list_files": list_files,
}


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a documentation assistant for a software engineering project.

Your task is to answer questions about the project by reading documentation files in the wiki directory.

Available tools:
- list_files: List files in a directory
- read_file: Read contents of a file

Strategy:
1. Use list_files to discover what files exist in the wiki directory
2. Use read_file to read relevant documentation files
3. Find the answer in the file contents
4. Include a source reference with the file path and section anchor (e.g., wiki/git-workflow.md#resolving-merge-conflicts)

Rules:
- Always include the source field in your final answer
- Make tool calls one at a time, not all at once
- If you find the answer, provide it with the source reference
- If you cannot find the answer after reading relevant files, say so

Respond with tool calls when you need to read files, or with a final answer when you have enough information."""


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

    # Load environment configuration
    load_env()

    # Run agent and get response
    response = run_agent(question)

    # Output JSON to stdout
    print(json.dumps(response))


if __name__ == "__main__":
    main()
