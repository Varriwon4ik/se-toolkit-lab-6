# Task 1 Plan: Call an LLM from Code

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus`

**Reasons:**
- 1000 free requests per day
- Works from Russia without VPN
- No credit card required
- Strong tool calling capabilities (for future tasks)

## Architecture

```
User question (CLI arg) → agent.py → HTTP POST → Qwen API (VM) → JSON response
```

## Implementation

### 1. Environment Configuration

Read from `.env.agent.secret`:
- `LLM_API_KEY` — API key for authentication
- `LLM_API_BASE` — Base URL (http://<vm-ip>:42005/v1)
- `LLM_MODEL` — Model name (qwen3-coder-plus)

### 2. Agent Structure

```python
#!/usr/bin/env python3
"""CLI agent that calls LLM and returns JSON answer."""

import json
import sys
import os
from pathlib import Path

# Load environment from .env.agent.secret
# Build API request to LLM_API_BASE/chat/completions
# Parse response and output JSON with:
#   - answer: string from LLM
#   - tool_calls: [] (empty for this task)
```

### 3. Output Format

```json
{"answer": "<LLM response>", "tool_calls": []}
```

- All output to stdout must be valid JSON
- Debug/logs go to stderr
- Exit code 0 on success
- Timeout: 60 seconds

### 4. Testing

Single regression test:
- Run `agent.py "What is 2+2?"` as subprocess
- Parse stdout as JSON
- Assert `answer` and `tool_calls` fields exist

## Files to Create

1. `plans/task-1.md` — This plan
2. `agent.py` — Main CLI agent
3. `AGENT.md` — Documentation
4. `tests/test_agent.py` — Regression test
