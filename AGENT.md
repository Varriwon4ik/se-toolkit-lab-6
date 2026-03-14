# Agent Documentation

## Overview

This agent is a CLI tool that connects to an LLM (Qwen Code API) with **tool calling capabilities** and an **agentic loop**. It can read files and list directories to answer questions about the project documentation, particularly the wiki.

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────────┐
│   User      │────▶│ agent.py │────▶│ Qwen Code API   │
│  (CLI arg)  │     │          │     │ (deployed on VM)│
└─────────────┘     └────┬─────┘     └─────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  Tools:          │
              │  - read_file     │
              │  - list_files    │
              └──────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  Agentic Loop    │
              │  (max 10 calls)  │
              └──────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  JSON output     │
              │  answer +        │
              │  source +        │
              │  tool_calls      │
              └──────────────────┘
```

## LLM Provider

**Provider:** Qwen Code API

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without VPN
- No credit card required
- Strong tool calling capabilities

## Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for authentication | `your-api-key` |
| `LLM_API_BASE` | Base URL of the LLM API | `http://10.93.25.222:42005/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

## Usage

```bash
# Run with a question
uv run agent.py "How do you resolve a merge conflict?"

# Output (JSON)
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "<final answer text>",
  "source": "wiki/file.md#section-anchor",
  "tool_calls": [
    {
      "tool": "tool_name",
      "args": {"arg_name": "value"},
      "result": "tool output"
    }
  ]
}
```

**Fields:**
- `answer` (required): The final answer from the LLM
- `source` (required): Reference to the wiki section (e.g., `wiki/git-workflow.md#section`)
- `tool_calls` (required): Array of all tool calls made during the agentic loop

**Notes:**
- All debug/log output goes to stderr
- Exit code 0 on success
- Timeout: 60 seconds
- Maximum 10 tool calls per question

## Tools

### 1. `read_file`

Read contents of a file from the project repository.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative path from project root (e.g., `wiki/git-workflow.md`) |

**Returns:** File contents as string, or error message.

**Security:**
- Rejects paths containing `../` (path traversal prevention)
- Only allows paths within project directory
- Returns error if file doesn't exist

### 2. `list_files`

List files and directories at a given path.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:** Newline-separated list of entries, or error message.

**Security:**
- Rejects paths containing `../` (path traversal prevention)
- Only allows paths within project directory
- Returns error if directory doesn't exist

## Agentic Loop

The agent uses an iterative loop to answer questions:

```
1. Send user question + tool schemas to LLM
2. Parse LLM response:
   - If tool_calls present:
     a. Execute each tool
     b. Append results as tool messages
     c. Loop back to step 1
   - If no tool_calls (final answer):
     a. Extract answer and source
     b. Output JSON and exit
3. Max 10 tool calls per question (safety limit)
```

### Message Format

**Initial message:**
```json
{"role": "user", "content": "<user question>"}
```

**Tool call from LLM:**
```json
{
  "role": "assistant",
  "tool_calls": [{"function": {"name": "read_file", "arguments": "{\"path\": \"wiki/git-workflow.md\"}"}}]
}
```

**Tool result:**
```json
{"role": "tool", "tool_call_id": "call_1", "content": "<file contents>"}
```

## System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki files
2. Use `read_file` to read relevant documentation
3. Include source reference with file path and section anchor
4. Make tool calls one at a time, not all at once
5. Provide final answer with source when enough information is gathered

## Implementation Details

### Environment Loading

The agent loads `.env.agent.secret` at startup using a simple key=value parser. Missing credentials cause an immediate error.

### API Communication

Uses Python's built-in `urllib.request` to make HTTP POST requests to the LLM API's `/chat/completions` endpoint with tool schemas.

### Path Security

The `validate_path()` function ensures:
- No `..` traversal in paths
- Paths are relative (not absolute)
- Resolved path is within project directory

### Error Handling

- Missing environment file → exit with error to stderr
- API connection failure → exit with error to stderr
- Invalid API response → exit with error to stderr
- Tool execution errors → returned as error message in result
- Timeout after 60 seconds → exit with error to stderr

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI agent with tools and agentic loop |
| `.env.agent.secret` | LLM configuration (gitignored) |
| `plans/task-2.md` | Implementation plan for Task 2 |
| `tests/test_agent.py` | Regression tests |

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Test questions:
- `"How do you resolve a merge conflict?"` — expects `read_file` tool call
- `"What files are in the wiki?"` — expects `list_files` tool call

## Future Extensions (Task 3)

- **Task 3:** Implement more advanced reasoning, possibly with additional tools like `query_api` to interact with the backend LMS.
