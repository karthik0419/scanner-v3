import subprocess, sys
subprocess.run([sys.executable, "paper_tracker.py", "reset"], input="yes\n", text=True, cwd="F:/projects/claude/scanner-v3")
subprocess.run([sys.executable, "paper_tracker.py", "init"], cwd="F:/projects/claude/scanner-v3")
