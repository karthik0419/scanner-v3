import ast, sys
files = [
    "F:/projects/claude/scanner-v3/scanner.py",
    "F:/projects/claude/scanner-v3/daily_scan.py",
    "F:/projects/claude/scanner-v3/paper_tracker.py",
    "F:/projects/claude/scanner-v3/backtester/engine.py",
    "F:/projects/claude/scanner-v3/patterns/double_bottom.py",
    "F:/projects/claude/scanner-v3/patterns/cup_handle.py",
    "F:/projects/claude/scanner-v3/patterns/cup_handle_monthly.py",
]
for f in files:
    try:
        code = open(f, encoding="utf-8").read()
        ast.parse(code)
        print("PASS syntax:", f.split("/")[-1])
    except SyntaxError as e:
        print("FAIL syntax:", f.split("/")[-1], "-", e.msg)
    except Exception as e:
        print("FAIL read:", f.split("/")[-1], "-", e)
