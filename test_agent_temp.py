import subprocess
import sys

result = subprocess.run(
    [sys.executable, "agent.py", "What is 2+2?"],
    capture_output=True,
    text=True,
    timeout=60,
)

print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("RETURN CODE:", result.returncode)
