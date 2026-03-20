# Task 3 Plan: The System Agent

## Overview

Extend the Task 2 documentation agent with a new `query_api` tool to interact with the deployed backend LMS. The agent will answer both static system questions (framework, ports, status codes) and data-dependent queries (item count, analytics).

## LLM Provider

**Provider:** Qwen Code API (same as Task 2)

**Model:** `qwen3-coder-plus`

**Why:** Already configured, strong tool calling capabilities.

## New Tool: `query_api`

### Purpose

Call the deployed backend LMS API to fetch data or test endpoints.

### Parameters

| Parameter | Type     | Required | Description                                      |
|-----------|----------|----------|--------------------------------------------------|
| `method`  | string   | Yes      | HTTP method (GET, POST, PUT, DELETE, etc.)       |
| `path`    | string   | Yes      | API endpoint path (e.g., `/items/`, `/analytics`)|
| `body`    | string   | No       | JSON request body for POST/PUT requests          |

### Returns

JSON string with:
- `status_code`: HTTP status code (int)
- `body`: Response body (parsed JSON or raw text)

### Authentication

The tool must authenticate using `LMS_API_KEY` from `.env.docker.secret`:
- Read `LMS_API_KEY` from environment
- Include `Authorization: Bearer <LMS_API_KEY>` header in API requests

### Implementation

```python
def query_api(method: str, path: str, body: str = None) -> str:
    """Call the backend LMS API with authentication."""
    import urllib.request
    import urllib.error
    import json
    import os

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
        data = json.dumps(body).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = {
                "status_code": response.status,
                "body": json.loads(response.read().decode("utf-8"))
            }
            return json.dumps(result)
    except urllib.error.HTTPError as e:
        result = {
            "status_code": e.code,
            "body": e.read().decode() if e.fp else ""
        }
        return json.dumps(result)
    except urllib.error.URLError as e:
        return json.dumps({"status_code": 0, "body": f"Connection error: {e.reason}"})
```

## Environment Variables

The agent must read ALL configuration from environment variables:

| Variable             | Purpose                              | Source              | Default                    |
|----------------------|--------------------------------------|---------------------|----------------------------|
| `LLM_API_KEY`        | LLM provider API key                 | `.env.agent.secret` | —                          |
| `LLM_API_BASE`       | LLM API endpoint URL                 | `.env.agent.secret` | —                          |
| `LLM_MODEL`          | Model name                           | `.env.agent.secret` | `qwen3-coder-plus`         |
| `LMS_API_KEY`        | Backend API key for query_api auth   | `.env.docker.secret`| —                          |
| `AGENT_API_BASE_URL` | Base URL for query_api               | Environment         | `http://localhost:42002`   |

**Important:** The autochecker injects different values at evaluation time. No hardcoded values!

## System Prompt Update

The system prompt must guide the LLM to choose the right tool:

1. **Wiki questions** (e.g., "According to the wiki...") → use `read_file` / `list_files`
2. **System facts** (e.g., "What framework...", "What port...") → use `read_file` on source code
3. **Data queries** (e.g., "How many items...", "What status code...") → use `query_api`
4. **Bug diagnosis** → use `query_api` to reproduce error, then `read_file` to find the bug

Updated system prompt strategy:
```
You are a documentation and system assistant for a software engineering project.

Available tools:
- list_files: List files in a directory
- read_file: Read contents of a file (use for wiki, source code, config)
- query_api: Call the backend API (use for data queries, status codes, analytics)

Strategy:
1. For wiki/documentation questions → use read_file on wiki/*.md
2. For system facts (framework, ports) → use read_file on source code
3. For data queries (item count, scores) → use query_api
4. For bug diagnosis → use query_api to reproduce, then read_file to diagnose

Always include source references for file-based answers.
```

## Agentic Loop

Same as Task 2 — max 10 tool calls, iterative execution.

## Output Format

Same as Task 2:
```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, ...}"}
  ]
}
```

## Implementation Steps

1. Create `plans/task-3.md` — this plan
2. Add `query_api` tool function with authentication
3. Add `query_api` to TOOL_SCHEMAS
4. Add `query_api` to TOOLS_MAP
5. Update SYSTEM_PROMPT for tool selection logic
6. Ensure environment variable loading reads both `.env.agent.secret` and `.env.docker.secret`
7. Update `AGENT.md` with new tool documentation
8. Add 2 regression tests:
   - `"What framework does the backend use?"` → expects `read_file`
   - `"How many items are in the database?"` → expects `query_api`
9. Run `run_eval.py` and iterate until all 10 questions pass
10. Document lessons learned in `plans/task-3.md`

## Benchmark Questions (from task-3.md)

| # | Question | Expected Tool | Keywords |
|---|----------|---------------|----------|
| 0 | Wiki: protect branch steps | read_file | branch, protect |
| 1 | Wiki: SSH connection steps | read_file | ssh, key, connect |
| 2 | What Python web framework? | read_file | FastAPI |
| 3 | List API router modules | list_files | items, interactions, analytics, pipeline |
| 4 | How many items in database? | query_api | number > 0 |
| 5 | Status code without auth? | query_api | 401, 403 |
| 6 | /analytics/completion-rate for lab-99 | query_api, read_file | ZeroDivisionError |
| 7 | /analytics/top-learners crash | query_api, read_file | TypeError, None |
| 8 | Request lifecycle (docker → db) | read_file | LLM judge (≥4 hops) |
| 9 | ETL idempotency | read_file | LLM judge (external_id) |

## Initial Eval Score

**Status:** Implementation complete. Local eval cannot run due to LLM API not available in this environment.

**Implementation completed:**
- [x] `query_api` tool added with authentication via `LMS_API_KEY`
- [x] Tool schema registered in `TOOL_SCHEMAS`
- [x] `TOOLS_MAP` updated with `query_api`
- [x] System prompt updated for tool selection logic
- [x] Environment loading reads both `.env.agent.secret` and `.env.docker.secret`
- [x] `AGENT.md` documentation updated (200+ words)
- [x] 2 regression tests added for `query_api` tool (in `tests/test_agent.py`)
- [x] Python syntax validated with `uv run python -m py_compile agent.py`
- [x] `query_api` tested directly and confirmed working with backend API
- [x] Environment variables load at module import time for test compatibility
- [x] Database seeded with 13 test items (4 labs, 9 tasks)

**Test verification:**
- `query_api('GET', '/items/')` returns 200 with item list ✓
- `LMS_API_KEY` loads from `.env.docker.secret` ✓
- Agent produces valid JSON output structure ✓

**Pending (requires LLM API access):**
- [ ] Run `uv run run_eval.py` and iterate until all 10 questions pass
- [ ] Verify autochecker bot benchmark passes

## Iteration Strategy

For each failing question when eval is run:
1. Check if the right tool was used
2. If wrong tool → improve system prompt
3. If right tool but wrong answer → check tool implementation
4. If tool returns error → debug the API call
5. Re-run `run_eval.py` and move to next failure

## Benchmark Readiness

The agent is ready for benchmark evaluation:

1. **Tool Implementation**: `query_api` correctly authenticates with `LMS_API_KEY` and returns structured JSON with `status_code` and `body`.

2. **Environment Configuration**: All LLM and backend API settings read from environment variables (`.env.agent.secret`, `.env.docker.secret`).

3. **System Prompt**: Updated to guide LLM tool selection:
   - Wiki questions → `read_file` / `list_files`
   - System facts → `read_file` on source code
   - Data queries → `query_api`
   - Bug diagnosis → `query_api` → `read_file`

4. **Test Coverage**: 5 regression tests in `tests/test_agent.py`:
   - Basic JSON output validation
   - Documentation agent: `read_file` for merge conflict question
   - Documentation agent: `list_files` for wiki directory question
   - System agent: `read_file` for framework question
   - System agent: `query_api` for item count question

5. **Backend API**: Running with 13 items in database for testing data queries.
