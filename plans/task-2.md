# Task 2 Plan: The Documentation Agent

## Overview

Extend the Task 1 agent with tools (`read_file`, `list_files`) and an agentic loop to answer questions about the project wiki.

## LLM Provider

**Provider:** Qwen Code API (same as Task 1)

**Model:** `qwen3-coder-plus`

**Why:** Strong tool calling capabilities, already configured.

## Tool Definitions

### 1. `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:**
- Reject paths containing `../` (path traversal)
- Only allow paths within project directory

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root

**Returns:** Newline-separated list of entries.

**Security:**
- Reject paths containing `../` (path traversal)
- Only allow paths within project directory

## Agentic Loop

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

## Message Format

**Initial message:**
```json
{
  "role": "user",
  "content": "<user question>"
}
```

**Tool call response from LLM:**
```json
{
  "role": "assistant",
  "tool_calls": [
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}}
  ]
}
```

**Tool result message:**
```json
{
  "role": "tool",
  "tool_call_id": "call_1",
  "content": "<file contents>"
}
```

## Output Format

```json
{
  "answer": "<final answer>",
  "source": "wiki/git-workflow.md#section-anchor",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to read relevant files
3. Include source reference (file path + section anchor) in the answer
4. Call tools step by step, not all at once

## Implementation Steps

1. Create `plans/task-2.md` — this plan
2. Implement `read_file` tool function
3. Implement `list_files` tool function
4. Add path security validation
5. Implement agentic loop (max 10 iterations)
6. Update LLM API call to include tool schemas
7. Parse tool calls from LLM response
8. Update output JSON to include `source` and populated `tool_calls`
9. Update `AGENT.md` with tools documentation
10. Add 2 regression tests

## Files to Modify/Create

| File | Action |
|------|--------|
| `plans/task-2.md` | Create |
| `agent.py` | Update with tools and loop |
| `AGENT.md` | Update with tools documentation |
| `tests/test_agent.py` | Add 2 tool-calling tests |
