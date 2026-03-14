import subprocess
import sys
import json

result = subprocess.run(
    [sys.executable, "agent.py", "What files are in the wiki?"],
    capture_output=True,
    text=True,
    timeout=60,
)

print("STDOUT:")
data = json.loads(result.stdout.strip())
print(json.dumps(data, indent=2))
print("\nSTDERR:", result.stderr)
print("\nRETURN CODE:", result.returncode)
