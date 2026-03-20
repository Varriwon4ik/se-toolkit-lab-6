# Agent Documentation

## Overview

This agent is a CLI tool that connects to an LLM (Qwen Code API) with **tool calling capabilities** and an **agentic loop**. It can read files, list directories, and query the backend LMS API to answer questions about the project documentation, source code, and live system data.

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────────┐
│   User      │────▶│ agent.py │────▶│ Qwen Code API   │
│  (CLI arg)  │     │          │     │ (deployed on VM)│
└─────────────┘     └────┬─────┘     └─────────────────┘
                         │
                         ▼
              ┌──────────────────────────┐
              │  Tools:                  │
              │  - read_file             │
              │  - list_files            │
              │  - query_api (NEW)       │
              └──────────────────────────┘
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

The agent reads configuration from environment variables and two optional files:

| Variable             | Purpose                              | Source              | Default                    |
|----------------------|--------------------------------------|---------------------|----------------------------|
| `LLM_API_KEY`        | LLM provider API key                 | `.env.agent.secret` | —                          |
| `LLM_API_BASE`       | LLM API endpoint URL                 | `.env.agent.secret` | —                          |
| `LLM_MODEL`          | Model name                           | `.env.agent.secret` | `qwen3-coder-plus`         |
| `LMS_API_KEY`        | Backend API key for query_api auth   | `.env.docker.secret`| —                          |
| `AGENT_API_BASE_URL` | Base URL for query_api               | Environment         | `http://localhost:42002`   |

**Important:** The autochecker injects different values at evaluation time. The agent never hardcodes credentials.

## Usage

```bash
# Run with a question
uv run agent.py "How do you resolve a merge conflict?"
uv run agent.py "How many items are in the database?"
uv run agent.py "What HTTP status code does /items/ return without auth?"

# Output (JSON)
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, ...}"}
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
- `source` (required): Reference to the wiki section (e.g., `wiki/git-workflow.md#section`) — may be empty for API queries
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

**Use cases:** Reading wiki documentation, source code files, configuration files.

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

**Use cases:** Discovering what files exist in a directory, finding router modules.

### 3. `query_api` (NEW in Task 3)

Call the backend LMS API with authentication.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | string | HTTP method (GET, POST, PUT, DELETE, etc.) |
| `path` | string | API endpoint path (e.g., `/items/`, `/analytics/completion-rate`) |
| `body` | string | Optional JSON request body for POST/PUT requests |

**Returns:** JSON string with `status_code` and `body` fields.

**Authentication:** Uses `LMS_API_KEY` from environment (via `.env.docker.secret`).

**Use cases:** Querying item counts, checking status codes, testing analytics endpoints, reproducing bugs.

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

1. Use `list_files` to discover wiki or source files
2. Use `read_file` to read wiki docs, source code, or configuration
3. Use `query_api` for data-dependent questions (item counts, status codes, analytics)
4. Include source reference with file path and section anchor for file-based answers
5. Make tool calls one at a time, not all at once
6. For bug diagnosis: use `query_api` to reproduce, then `read_file` to find the bug

### Tool Selection Strategy

The LLM decides which tool to use based on the question type:

| Question Type | Example | Tool |
|--------------|---------|------|
| Wiki documentation | "According to the wiki, how do you protect a branch?" | `read_file`, `list_files` |
| System facts | "What framework does the backend use?" | `read_file` (source code) |
| Data queries | "How many items are in the database?" | `query_api` |
| Status codes | "What status code does /items/ return without auth?" | `query_api` |
| Bug diagnosis | "Why does /analytics/completion-rate crash for lab-99?" | `query_api` → `read_file` |
| Architecture | "Explain the request lifecycle from browser to database" | `read_file` (config files) |

## Implementation Details

### Environment Loading

The agent loads both `.env.agent.secret` (LLM config) and `.env.docker.secret` (backend API config) at startup. If files are missing, it relies on environment variables (useful for autochecker evaluation).

### API Communication

Uses Python's built-in `urllib.request` to make HTTP POST requests to the LLM API's `/chat/completions` endpoint with tool schemas.

### Path Security

The `validate_path()` function ensures:
- No `..` traversal in paths
- Paths are relative (not absolute)
- Resolved path is within project directory

### Error Handling

- Missing environment files → gracefully uses environment variables
- API connection failure → exit with error to stderr
- Invalid API response → exit with error to stderr
- Tool execution errors → returned as error message in result
- Timeout after 60 seconds → exit with error to stderr

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI agent with tools and agentic loop |
| `.env.agent.secret` | LLM configuration (gitignored) |
| `.env.docker.secret` | Backend API configuration (gitignored) |
| `plans/task-3.md` | Implementation plan for Task 3 |
| `tests/test_agent.py` | Regression tests (including query_api tests) |

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Test questions:
- `"How do you resolve a merge conflict?"` — expects `read_file` tool call
- `"What files are in the wiki?"` — expects `list_files` tool call
- `"What Python web framework does the backend use?"` — expects `read_file` tool call
- `"How many items are in the database?"` — expects `query_api` tool call

## Benchmark Evaluation

Run the local benchmark:

```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all classes:
- Wiki lookup (branch protection, SSH)
- System facts (framework, router modules)
- Data queries (item count, status codes)
- Bug diagnosis (ZeroDivisionError, TypeError)
- Reasoning (request lifecycle, ETL idempotency)

## Lessons Learned

1. **Tool descriptions matter:** The LLM needs clear guidance on when to use each tool. Initially, the agent would try to use `read_file` for data queries. Adding explicit examples in the system prompt ("How many items..." → `query_api`) fixed this.

2. **Authentication is critical:** The `query_api` tool must include the `LMS_API_KEY` header. Without it, the backend returns 401/403 errors. Reading credentials from environment variables (not hardcoded) ensures the autochecker can inject its own values.

3. **Error handling in query_api:** The tool must gracefully handle HTTP errors (404, 500) and connection errors. Returning structured JSON with `status_code` and `body` allows the LLM to understand what went wrong.

4. **Max tool calls:** The 10-call limit prevents infinite loops but can be tight for complex multi-step questions. The agent should be efficient in its tool usage.

5. **Source field flexibility:** For API queries, the `source` field may be empty since there's no file reference. The system prompt was updated to only require source references for file-based answers.

## Final Eval Score

To be added after running the full benchmark.
