# Agent Documentation

## Overview

This agent is a CLI tool that connects to an LLM (Qwen Code API) and answers questions. It serves as the foundation for the agentic system that will be extended with tools and a decision loop in subsequent tasks.

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────────┐
│   User      │────▶│ agent.py │────▶│ Qwen Code API   │
│  (CLI arg)  │     │          │     │ (deployed on VM)│
└─────────────┘     └──────────┘     └─────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ JSON output  │
                    │ answer +     │
                    │ tool_calls   │
                    └──────────────┘
```

## LLM Provider

**Provider:** Qwen Code API

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without VPN
- No credit card required
- OpenAI-compatible API

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
uv run agent.py "What does REST stand for?"

# Output (JSON)
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "<LLM response text>",
  "tool_calls": []
}
```

**Fields:**
- `answer` (required): The LLM's response to the question
- `tool_calls` (required): Array of tool calls (empty for Task 1, populated in Task 2)

**Notes:**
- All debug/log output goes to stderr
- Exit code 0 on success
- Timeout: 60 seconds

## Implementation Details

### Environment Loading

The agent loads `.env.agent.secret` at startup using a simple key=value parser. Missing credentials cause an immediate error.

### API Communication

Uses Python's built-in `urllib.request` to make HTTP POST requests to the LLM API's `/chat/completions` endpoint.

### Error Handling

- Missing environment file → exit with error to stderr
- API connection failure → exit with error to stderr
- Invalid API response → exit with error to stderr
- Timeout after 60 seconds → exit with error to stderr

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI agent |
| `.env.agent.secret` | LLM configuration (gitignored) |
| `plans/task-1.md` | Implementation plan |
| `tests/test_agent.py` | Regression tests |

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

## Future Extensions (Tasks 2-3)

- **Task 2:** Add tools (e.g., `read_file`, `query_api`) and populate `tool_calls`
- **Task 3:** Implement agentic loop for multi-step reasoning
