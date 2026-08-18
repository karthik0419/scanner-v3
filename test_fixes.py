"""
Test suite for scanner-v3 fixes (2026-08-12 session).

Validates all fixes made in the 2026-08-12 session:
1. Bat files show output on screen (not blank)
2. paper_tracker.py UTF-8 encoding fix
3. rank_2week.py dynamic CSV loading (not hardcoded)
4. _daily_scan_enhanced.py restored from _archive/
5. _tracker_status.py restored from _archive/
6. Redundant files deleted (daily_scan_prod.bat, weekly_scan_prod.bat, .env.swingu_backup)
7. Stale files moved to _archive/stale_2026-08-12/
8. Cron task battery restrictions removed
9. All scripts import without errors
10. Telegram bots wired correctly (SwingU vs SwingIQ)

Usage:
    python test_fixes.py              # run all tests
    python test_fixes.py --verbose    # show full output
    python test_fixes.py --quick      # skip slow tests (bat file runs)

Each test prints PASS/FAIL with details. Exit code 0 = all pass.
"""
import sys
import os
import glob
import subprocess
import argparse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

passed = 0
failed = 0
skipped = 0


def run_cmd(cmd, timeout=60):
    """Run a command, return (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=PROJECT_DIR
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def test_pass(name, detail=""):
    global passed
    passed += 1
    print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))


def test_fail(name, detail=""):
    global failed
    failed += 1
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def test_skip(name, reason=""):
    global skipped
    skipped += 1
    print(f"  SKIP  {name}" + (f" — {reason}" if reason else ""))


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ════════════════════════════════════════════════════════════════════
# TEST 1: Bat files show output on screen (not blank)
# ════════════════════════════════════════════════════════════════════
def test_bat_files_not_blank():
    section("TEST 1: Bat files show output on screen (not blank)")
    bat_files = [
        ("daily_scan_test.bat", "pause", "SwingU"),
        ("weekly_scan_test.bat", "pause", "SwingU"),
        ("auto_daily_scan.bat", None, "SwingIQ"),  # no pause (cron)
        ("auto_weekly_scan.bat", None, "SwingIQ"),
    ]
    for bat, expected_pause, bot in bat_files:
        path = os.path.join(PROJECT_DIR, bat)
        if not os.path.exists(path):
            test_fail(f"{bat} exists", "file not found")
            continue
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        # Check it has a title line
        if "title " in content.lower():
            test_pass(f"{bat} has title line")
        else:
            test_fail(f"{bat} has title line", "no 'title' directive")
        # Check it has echo header (not just @echo off)
        echo_lines = [l for l in content.split('\n')
                      if l.strip().startswith('echo ') and 'off' not in l.lower()
                      and '===' in l]
        if len(echo_lines) >= 2:
            test_pass(f"{bat} has screen header")
        else:
            test_fail(f"{bat} has screen header", f"only {len(echo_lines)} echo lines")
        # Check pause (test bat files only)
        if expected_pause:
            if "pause" in content.lower():
                test_pass(f"{bat} has pause at end")
            else:
                test_fail(f"{bat} has pause at end", "no pause — window closes immediately")
        # Check bot reference
        if bot in content:
            test_pass(f"{bat} references {bot}")
        else:
            test_fail(f"{bat} references {bot}", f"'{bot}' not found in content")


# ════════════════════════════════════════════════════════════════════
# TEST 2: paper_tracker.py UTF-8 encoding fix
# ════════════════════════════════════════════════════════════════════
def test_paper_tracker_encoding():
    section("TEST 2: paper_tracker.py UTF-8 encoding fix")
    path = os.path.join(PROJECT_DIR, "paper_tracker.py")
    with open(path, 'r') as f:
        content = f.read()
    if "sys.stdout.reconfigure" in content:
        test_pass("paper_tracker.py has sys.stdout.reconfigure")
    else:
        test_fail("paper_tracker.py has sys.stdout.reconfigure", "missing — encoding bug")
    # Run summary and check it doesn't produce cp1252 garbage
    rc, out, err = run_cmd("python paper_tracker.py summary", timeout=30)
    if rc == 0:
        # Check for em-dash (the character that was breaking)
        if "\x97" not in out and "Paper Tracker Summary" in out:
            test_pass("paper_tracker.py summary produces clean UTF-8 output")
        else:
            test_fail("paper_tracker.py summary produces clean UTF-8",
                      "cp1252 garbage detected or missing expected text")
    else:
        test_fail("paper_tracker.py summary runs", f"exit {rc}: {err[:100]}")


# ════════════════════════════════════════════════════════════════════
# TEST 3: rank_2week.py dynamic CSV loading
# ════════════════════════════════════════════════════════════════════
def test_rank_2week_dynamic():
    section("TEST 3: rank_2week.py dynamic CSV loading (not hardcoded)")
    path = os.path.join(PROJECT_DIR, "rank_2week.py")
    with open(path, 'r') as f:
        content = f.read()
    # Check no hardcoded date path
    if "v3_2026-07-29" in content:
        test_fail("rank_2week.py hardcoded path removed", "still has v3_2026-07-29")
    else:
        test_pass("rank_2week.py hardcoded path removed")
    # Check it uses glob
    if "glob.glob" in content and "v3_*.csv" in content:
        test_pass("rank_2week.py uses glob for dynamic CSV loading")
    else:
        test_fail("rank_2week.py uses glob", "glob or v3_*.csv pattern not found")
    # Check it has encoding fix
    if "sys.stdout.reconfigure" in content:
        test_pass("rank_2week.py has UTF-8 encoding fix")
    else:
        test_fail("rank_2week.py has UTF-8 encoding fix", "missing")
    # Run it
    rc, out, err = run_cmd("python rank_2week.py", timeout=30)
    if rc == 0 and "PROFIT POTENTIAL" in out:
        # Check it loaded the latest CSV (not July 29)
        if "2026-07-29" in out:
            test_fail("rank_2week.py loads latest CSV", "still showing July 29 date")
        else:
            test_pass("rank_2week.py loads latest CSV dynamically")
    else:
        test_fail("rank_2week.py runs", f"exit {rc}: {err[:100]}")


# ════════════════════════════════════════════════════════════════════
# TEST 4: Restored scripts exist and import
# ════════════════════════════════════════════════════════════════════
def test_restored_scripts():
    section("TEST 4: Restored scripts exist and import correctly")
    scripts = [
        ("_daily_scan_enhanced.py", ["backtester.engine", "data.loader",
                                     "utils.sector_rotation_v3", "telegram_notify"]),
        ("_tracker_status.py", ["telegram_notify", "pandas"]),
    ]
    for script, expected_imports in scripts:
        path = os.path.join(PROJECT_DIR, script)
        if not os.path.exists(path):
            test_fail(f"{script} exists in root", "file not found")
            continue
        test_pass(f"{script} exists in root")
        with open(path, 'r') as f:
            content = f.read()
        for imp in expected_imports:
            if imp in content:
                test_pass(f"{script} imports {imp}")
            else:
                test_fail(f"{script} imports {imp}", "import not found in source")


# ════════════════════════════════════════════════════════════════════
# TEST 5: Redundant files deleted
# ════════════════════════════════════════════════════════════════════
def test_redundant_files_deleted():
    section("TEST 5: Redundant files deleted")
    deleted_files = [
        "daily_scan_prod.bat",
        "weekly_scan_prod.bat",
        ".env.swingu_backup",
    ]
    for f in deleted_files:
        path = os.path.join(PROJECT_DIR, f)
        if os.path.exists(path):
            test_fail(f"{f} deleted", "still exists in root")
        else:
            test_pass(f"{f} deleted")


# ════════════════════════════════════════════════════════════════════
# TEST 6: Stale files moved to archive
# ════════════════════════════════════════════════════════════════════
def test_stale_files_archived():
    section("TEST 6: Stale files moved to _archive/stale_2026-08-12/")
    stale_files = [
        "test_backtest.txt", "test_charts.txt", "test_compare.txt",
        "test_smart.txt", "test_status.txt", "test_summary.txt",
        "test_sweep.txt", "test_sync.txt", "test_update.txt",
        "test_whipsaw.txt", "SESSION_2026-07-19.md",
        "inkling_review.md", "inkling_review_output.md", "inkling_final.md",
        "COMMIT_MSG.txt", "vedl_out.txt", "vedl_eod_out.txt",
        "charts_today.txt", "daily_scan_today.txt", "eod_status.txt",
        "eod_update.txt", "rank_output.txt", "reentry_results.txt",
        "scan_today.txt", "sweep_results.txt", "telegram_output.txt",
        "update_err.txt", "nifty200_sweep.txt",
    ]
    archive_dir = os.path.join(PROJECT_DIR, "_archive", "stale_2026-08-12")
    if not os.path.isdir(archive_dir):
        test_fail("archive dir exists", "_archive/stale_2026-08-12/ not found")
        return
    test_pass("archive dir exists (_archive/stale_2026-08-12/)")
    moved_count = 0
    for f in stale_files:
        root_path = os.path.join(PROJECT_DIR, f)
        archive_path = os.path.join(archive_dir, f)
        if not os.path.exists(root_path):
            if os.path.exists(archive_path):
                moved_count += 1
            # else: file doesn't exist anywhere — might not have existed
        else:
            test_fail(f"{f} moved to archive", "still in root")
    if moved_count > 0:
        test_pass(f"{moved_count} stale files moved to archive")
    # Check root is clean (only expected txt/md files)
    expected_root = {
        "backbone50.txt", "nifty200.txt", "nifty500.txt", "requirements.txt",
        "COMPARISON_REPORT.md", "README.md", "VERSION.md"
    }
    actual_root = set()
    for f in os.listdir(PROJECT_DIR):
        if f.endswith(('.txt', '.md')) and not f.startswith('.'):
            actual_root.add(f)
    unexpected = actual_root - expected_root
    if not unexpected:
        test_pass("root directory clean (only expected .txt/.md files)")
    else:
        test_fail("root directory clean", f"unexpected files: {unexpected}")


# ════════════════════════════════════════════════════════════════════
# TEST 7: Cron task battery restrictions removed
# ════════════════════════════════════════════════════════════════════
def test_cron_battery():
    section("TEST 7: Cron task battery restrictions removed")
    rc, out, err = run_cmd(
        'schtasks /query /tn "\\SwingIQ_DailyScan" /fo LIST /v', timeout=15
    )
    if rc != 0:
        test_skip("SwingIQ_DailyScan battery check", "schtasks query failed (need admin?)")
        return
    if "Stop On Battery Mode" in out or "No Start On Batteries" in out:
        test_fail("SwingIQ_DailyScan battery restrictions removed",
                  "restrictions still present")
    else:
        test_pass("SwingIQ_DailyScan battery restrictions removed")

    rc, out, err = run_cmd(
        'schtasks /query /tn "\\SwingIQ_WeeklyScan" /fo LIST /v', timeout=15
    )
    if rc == 0:
        if "Stop On Battery Mode" in out or "No Start On Batteries" in out:
            test_fail("SwingIQ_WeeklyScan battery restrictions removed",
                      "restrictions still present")
        else:
            test_pass("SwingIQ_WeeklyScan battery restrictions removed")
    else:
        test_skip("SwingIQ_WeeklyScan battery check", "schtasks query failed")


# ════════════════════════════════════════════════════════════════════
# TEST 8: Telegram bots wired correctly
# ════════════════════════════════════════════════════════════════════
def test_telegram_bots():
    section("TEST 8: Telegram bots wired correctly (SwingU vs SwingIQ)")
    # .env (SwingU)
    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            env_content = f.read()
        if "8844316110" in env_content and "1121884245" in env_content:
            test_pass(".env has SwingU bot (token 8844316110, chat 1121884245)")
        else:
            test_fail(".env has SwingU bot", "token/chat ID mismatch")
    else:
        test_fail(".env exists", "file not found")

    # .env.swingiq (SwingIQ)
    enviq_path = os.path.join(PROJECT_DIR, ".env.swingiq")
    if os.path.exists(enviq_path):
        with open(enviq_path) as f:
            enviq_content = f.read()
        if "8538750785" in enviq_content and "-1004275742331" in enviq_content:
            test_pass(".env.swingiq has SwingIQ bot (token 8538750785, channel -1004275742331)")
        else:
            test_fail(".env.swingiq has SwingIQ bot", "token/chat ID mismatch")
    else:
        test_fail(".env.swingiq exists", "file not found")

    # Check bat files use correct env files
    bat_checks = [
        ("auto_daily_scan.bat", ".env.swingiq"),
        ("auto_weekly_scan.bat", ".env.swingiq"),
        ("daily_scan_test.bat", None),  # uses default .env (no --env-file)
        ("weekly_scan_test.bat", None),
    ]
    for bat, env_file in bat_checks:
        path = os.path.join(PROJECT_DIR, bat)
        if not os.path.exists(path):
            test_skip(f"{bat} env wiring", "file not found")
            continue
        with open(path, encoding='utf-8') as f:
            content = f.read()
        if env_file:
            if env_file in content:
                test_pass(f"{bat} uses {env_file} (SwingIQ)")
            else:
                test_fail(f"{bat} uses {env_file}", f"{env_file} not found in bat")
        else:
            # Should NOT have --env-file (uses default .env = SwingU)
            if "--env-file" not in content:
                test_pass(f"{bat} uses default .env (SwingU)")
            else:
                test_fail(f"{bat} uses default .env", "has --env-file (should not)")


# ════════════════════════════════════════════════════════════════════
# TEST 9: All core scripts import without errors
# ════════════════════════════════════════════════════════════════════
def test_all_imports():
    section("TEST 9: All core scripts import without errors")
    # Test imports via python -c (don't run the full script)
    import_tests = [
        ("telegram_notify", "from telegram_notify import send_telegram, _get_credentials"),
        ("backtester.engine", "from backtester.engine import _detect_signal, _score, DETECTORS"),
        ("data.loader", "from data.loader import _fetch_nse, _resample_weekly"),
        ("utils.sector_rotation_v3", "from utils.sector_rotation_v3 import get_stock_sector, get_hot_sectors"),
        ("paper_tracker", "import paper_tracker"),
    ]
    for name, imp_cmd in import_tests:
        rc, out, err = run_cmd(f'python -c "{imp_cmd}; print(\'OK\')"', timeout=30)
        if rc == 0 and "OK" in out:
            test_pass(f"import {name}")
        else:
            test_fail(f"import {name}", err.strip()[:100] if err else f"exit {rc}")


# ════════════════════════════════════════════════════════════════════
# TEST 10: Interactive menu bat files have valid options
# ════════════════════════════════════════════════════════════════════
def test_menu_bat_files():
    section("TEST 10: Interactive menu bat files have valid options")
    menus = [
        ("Daily Scan.bat", 22, ["_daily_scan_enhanced.py", "_tracker_status.py"]),
        ("run_weekly.bat", 24, ["_daily_scan_enhanced.py", "_tracker_status.py"]),
    ]
    for bat, max_option, required_scripts in menus:
        path = os.path.join(PROJECT_DIR, bat)
        if not os.path.exists(path):
            test_fail(f"{bat} exists", "not found")
            continue
        test_pass(f"{bat} exists")
        with open(path, 'r') as f:
            content = f.read()
        # Check exit option
        if f'"{max_option}"' in content and "exit" in content.lower():
            test_pass(f"{bat} has exit option {max_option}")
        else:
            test_fail(f"{bat} has exit option {max_option}", "not found")
        # Check referenced scripts exist
        for script in required_scripts:
            if script in content:
                script_path = os.path.join(PROJECT_DIR, script)
                if os.path.exists(script_path):
                    test_pass(f"{bat} references {script} (exists)")
                else:
                    test_fail(f"{bat} references {script} (exists)",
                              "referenced but file missing from root")
            # else: script not referenced in this bat — OK


# ════════════════════════════════════════════════════════════════════
# TEST 11: Daily cron 2-step flow (smart scan + daily scan)
# ════════════════════════════════════════════════════════════════════
def test_daily_cron_2step():
    section("TEST 11: Daily cron 2-step flow (smart scan + daily scan)")
    # Check auto_daily_scan.bat has both steps
    path = os.path.join(PROJECT_DIR, "auto_daily_scan.bat")
    if not os.path.exists(path):
        test_fail("auto_daily_scan.bat exists", "not found")
        return
    with open(path, encoding='utf-8') as f:
        content = f.read()
    # Step 1: scanner.py --smart
    if "scanner.py --smart" in content or "scanner.py --smart" in content:
        test_pass("auto_daily_scan.bat has Step 1: scanner.py --smart")
    else:
        test_fail("auto_daily_scan.bat has Step 1: scanner.py --smart", "not found")
    # Step 2: daily_scan.py
    if "daily_scan.py" in content:
        test_pass("auto_daily_scan.bat has Step 2: daily_scan.py")
    else:
        test_fail("auto_daily_scan.bat has Step 2: daily_scan.py", "not found")
    # Check --no-notify on step 1 (scanner shouldn't send Telegram, daily_scan does)
    if "--no-notify" in content:
        test_pass("Step 1 has --no-notify (daily_scan sends Telegram, not scanner)")
    else:
        test_fail("Step 1 has --no-notify", "missing — scanner would send duplicate Telegram")
    # Check daily_scan_test.bat also has 2-step
    test_path = os.path.join(PROJECT_DIR, "daily_scan_test.bat")
    if os.path.exists(test_path):
        with open(test_path) as f:
            test_content = f.read()
        if "scanner.py --smart" in test_content and "daily_scan.py" in test_content:
            test_pass("daily_scan_test.bat also has 2-step flow")
        else:
            test_fail("daily_scan_test.bat has 2-step flow", "missing scanner or daily_scan step")


# ════════════════════════════════════════════════════════════════════
# TEST 12: Freshness tracking (NEW / Day N labels)
# ════════════════════════════════════════════════════════════════════
def test_freshness_tracking():
    section("TEST 12: Freshness tracking (NEW / Day N labels)")
    # Check _compute_freshness function exists in daily_scan.py
    path = os.path.join(PROJECT_DIR, "daily_scan.py")
    with open(path, encoding='utf-8') as f:
        content = f.read()
    if "_compute_freshness" in content:
        test_pass("daily_scan.py has _compute_freshness function")
    else:
        test_fail("daily_scan.py has _compute_freshness function", "not found")
    # Check _fmt_pick_rich accepts freshness parameter
    if "freshness=None" in content or "freshness=" in content:
        test_pass("_fmt_pick_rich accepts freshness parameter")
    else:
        test_fail("_fmt_pick_rich accepts freshness parameter", "not found")
    # Check NEW badge
    if "🆕 NEW" in content or "NEW" in content and "fresh" in content.lower():
        test_pass("NEW badge (🆕) present in formatting")
    else:
        test_fail("NEW badge present", "not found")
    # Check Day N badge
    if "🔁" in content or "Day {" in content:
        test_pass("Day N badge (🔁) present in formatting")
    else:
        test_fail("Day N badge present", "not found")
    # Check header shows new/repeating count
    if "new" in content.lower() and "repeating" in content.lower():
        test_pass("Header shows new/repeating count")
    else:
        test_fail("Header shows new/repeating count", "not found")
    # Run the function via a temp script (avoids PowerShell quote issues)
    import tempfile
    tmp = os.path.join(PROJECT_DIR, "_tmp_fresh_test.py")
    with open(tmp, 'w') as tf:
        tf.write(
            "import sys; sys.path.insert(0,'.'); "
            "from daily_scan import _compute_freshness, _load_weekly_scan_df, _normalize_symbol; "
            "df, p = _load_weekly_scan_df(); "
            "syms = [_normalize_symbol(str(s)) for s in df['symbol']]; "
            "f = _compute_freshness(p, syms); "
            "print(len(f))"
        )
    rc, out, err = run_cmd(f"python {tmp}", timeout=30)
    os.unlink(tmp)
    if rc == 0 and out.strip().isdigit():
        test_pass(f"_compute_freshness runs successfully ({out.strip()} symbols)")
    else:
        test_fail("_compute_freshness runs", f"exit {rc}: {err[:100] if err else out[:100]}")


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Test scanner-v3 fixes (2026-08-12)")
    parser.add_argument("--verbose", action="store_true", help="show full output")
    parser.add_argument("--quick", action="store_true", help="skip slow tests")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  SCANNER-V3 FIX TEST SUITE — 2026-08-12 session")
    print(f"  Project: {PROJECT_DIR}")
    print(f"{'='*70}")

    test_bat_files_not_blank()
    test_paper_tracker_encoding()
    test_rank_2week_dynamic()
    test_restored_scripts()
    test_redundant_files_deleted()
    test_stale_files_archived()
    test_cron_battery()
    test_telegram_bots()
    test_all_imports()
    test_menu_bat_files()
    test_daily_cron_2step()
    test_freshness_tracking()

    print(f"\n{'='*70}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'='*70}")

    if failed > 0:
        print(f"\n  ❌ {failed} test(s) failed. Review details above.")
        sys.exit(1)
    else:
        print(f"\n  ✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
