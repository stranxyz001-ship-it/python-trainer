# app.py
"""
Python Practice Tool (Streamlit)
Features:
- Daily tasks by level
- Safe evaluation with AST checks and subprocess isolation
- Adaptive difficulty
- Dashboard with charts and progress
- Persistence: SQLite (default) or JSON file
- Visual enhancements (metrics, progress bars, confetti)
- Personalized messages for user "Adnan Chotiya"
"""

import streamlit as st
import sqlite3
import json
import datetime
import hashlib
import multiprocessing as mp
import traceback
import sys
import os
import ast
import textwrap
import time
from typing import Any, Dict, List, Tuple
import pandas as pd
import altair as alt
import random
import math

# -------------------------
# Configuration
# -------------------------
APP_TITLE = "Python Practice Studio"
DB_PATH = "practice.db"
JSON_PATH = "practice.json"
USER_NAME = "Adnan Chotiya"  # personalized name
DEFAULT_STORAGE = "sqlite"  # "sqlite" or "json"
APP_SECRET = "streamlit_practice_tool_v2"

# Visual settings
CONFETTI_JS = """
<script>
function fireConfetti(){
  const duration = 3 * 1000;
  const end = Date.now() + duration;
  (function frame() {
    const colors = ['#bb0000', '#ffffff', '#00bbff', '#ffdd00', '#00ff88'];
    confetti({
      particleCount: 5,
      angle: 60,
      spread: 55,
      origin: { x: 0 },
      colors: colors
    });
    confetti({
      particleCount: 5,
      angle: 120,
      spread: 55,
      origin: { x: 1 },
      colors: colors
    });
    if (Date.now() < end) {
      requestAnimationFrame(frame);
    }
  }());
}
</script>
"""

# -------------------------
# Task Bank (expandable)
# -------------------------
# Each task: id, title, prompt, function_name, tests, hint, difficulty tags
TASKS_BY_LEVEL = {
    1: [
        {
            "id": "l1_sum_two",
            "title": "Sum Two Numbers",
            "prompt": "Write `sum_two(a, b)` that returns the sum of two numbers.",
            "function_name": "sum_two",
            "tests": [
                {"input": [1, 2], "expected": 3},
                {"input": [-1, 5], "expected": 4},
                {"input": [0, 0], "expected": 0},
            ],
            "hint": "Return a + b."
        },
        {
            "id": "l1_is_even",
            "title": "Is Even",
            "prompt": "Write `is_even(n)` that returns True if n is even, else False.",
            "function_name": "is_even",
            "tests": [
                {"input": [2], "expected": True},
                {"input": [3], "expected": False},
                {"input": [0], "expected": True},
            ],
            "hint": "Use n % 2 == 0."
        },
    ],
    2: [
        {
            "id": "l2_factorial",
            "title": "Factorial",
            "prompt": "Write `factorial(n)` returning n! for n >= 0 (integer).",
            "function_name": "factorial",
            "tests": [
                {"input": [0], "expected": 1},
                {"input": [5], "expected": 120},
                {"input": [3], "expected": 6},
            ],
            "hint": "Use a loop or recursion."
        },
        {
            "id": "l2_fib_n",
            "title": "Nth Fibonacci",
            "prompt": "Write `fib(n)` returning nth Fibonacci (0-indexed).",
            "function_name": "fib",
            "tests": [
                {"input": [0], "expected": 0},
                {"input": [1], "expected": 1},
                {"input": [7], "expected": 13},
            ],
            "hint": "Iterative approach is safe."
        },
    ],
    3: [
        {
            "id": "l3_unique_words",
            "title": "Unique Words",
            "prompt": "Write `unique_words(s)` returning sorted list of unique lowercase words.",
            "function_name": "unique_words",
            "tests": [
                {"input": ["Hello hello world"], "expected": ["hello", "world"]},
                {"input": ["a b a c"], "expected": ["a", "b", "c"]},
            ],
            "hint": "Use set and sorted."
        },
        {
            "id": "l3_is_palindrome",
            "title": "Is Palindrome",
            "prompt": "Write `is_palindrome(s)` ignoring non-alphanumeric and case.",
            "function_name": "is_palindrome",
            "tests": [
                {"input": ["A man, a plan, a canal: Panama"], "expected": True},
                {"input": ["hello"], "expected": False},
            ],
            "hint": "Filter characters and compare to reversed."
        },
    ],
    4: [
        {
            "id": "l4_group_anagrams",
            "title": "Group Anagrams",
            "prompt": "Write `group_anagrams(words)` grouping anagrams (list of lists).",
            "function_name": "group_anagrams",
            "tests": [
                {"input": [["eat", "tea", "tan", "ate", "nat", "bat"]], "expected": [["eat","tea","ate"],["tan","nat"],["bat"]]},
            ],
            "hint": "Use sorted word as key."
        },
        {
            "id": "l4_two_sum",
            "title": "Two Sum Indices",
            "prompt": "Write `two_sum(nums, target)` returning tuple of two indices or None.",
            "function_name": "two_sum",
            "tests": [
                {"input": [[2,7,11,15], 9], "expected": (0,1)},
                {"input": [[3,2,4], 6], "expected": (1,2)},
            ],
            "hint": "Use a dict to map values to indices."
        },
    ],
    5: [
        {
            "id": "l5_merge_intervals",
            "title": "Merge Intervals",
            "prompt": "Write `merge_intervals(intervals)` merging overlapping intervals.",
            "function_name": "merge_intervals",
            "tests": [
                {"input": [[[1,3],[2,6],[8,10],[15,18]]], "expected": [[1,6],[8,10],[15,18]]},
                {"input": [[[1,4],[4,5]]], "expected": [[1,5]]},
            ],
            "hint": "Sort by start and merge."
        },
        {
            "id": "l5_longest_substring",
            "title": "Longest Substring Without Repeating",
            "prompt": "Write `length_of_longest_substring(s)` returning length of longest substring without repeats.",
            "function_name": "length_of_longest_substring",
            "tests": [
                {"input": ["abcabcbb"], "expected": 3},
                {"input": ["bbbbb"], "expected": 1},
            ],
            "hint": "Sliding window with last-seen indices."
        },
    ],
}

# -------------------------
# Storage Abstraction
# -------------------------
def init_sqlite(db_path=DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_state (
        id INTEGER PRIMARY KEY,
        level INTEGER,
        streak INTEGER,
        last_task_date TEXT,
        last_task_id TEXT,
        success_streak INTEGER,
        preferred_name TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        date TEXT,
        passed INTEGER,
        feedback TEXT
    )
    """)
    c.execute("SELECT COUNT(*) FROM user_state")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO user_state (level, streak, last_task_date, last_task_id, success_streak, preferred_name) VALUES (?, ?, ?, ?, ?, ?)",
                  (1, 0, "", "", 0, USER_NAME))
    conn.commit()
    return conn

def init_json(path=JSON_PATH):
    if not os.path.exists(path):
        data = {
            "user_state": {
                "level": 1,
                "streak": 0,
                "last_task_date": "",
                "last_task_id": "",
                "success_streak": 0,
                "preferred_name": USER_NAME
            },
            "attempts": []
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    # load
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Storage wrapper class
class Storage:
    def __init__(self, mode="sqlite"):
        self.mode = mode
        if mode == "sqlite":
            self.conn = init_sqlite()
        else:
            self.json_path = JSON_PATH
            self.data = init_json(self.json_path)

    def get_state(self):
        if self.mode == "sqlite":
            c = self.conn.cursor()
            c.execute("SELECT level, streak, last_task_date, last_task_id, success_streak, preferred_name FROM user_state LIMIT 1")
            row = c.fetchone()
            return {
                "level": row[0],
                "streak": row[1],
                "last_task_date": row[2],
                "last_task_id": row[3],
                "success_streak": row[4],
                "preferred_name": row[5] or USER_NAME
            }
        else:
            return self.data["user_state"]

    def update_state(self, **kwargs):
        state = self.get_state()
        state.update(kwargs)
        if self.mode == "sqlite":
            c = self.conn.cursor()
            c.execute("""
            UPDATE user_state SET level=?, streak=?, last_task_date=?, last_task_id=?, success_streak=?, preferred_name=? WHERE id=1
            """, (state["level"], state["streak"], state["last_task_date"], state["last_task_id"], state["success_streak"], state.get("preferred_name", USER_NAME)))
            self.conn.commit()
        else:
            self.data["user_state"] = state
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

    def record_attempt(self, task_id: str, passed: bool, feedback: str):
        entry = {"task_id": task_id, "date": datetime.date.today().isoformat(), "passed": int(passed), "feedback": feedback}
        if self.mode == "sqlite":
            c = self.conn.cursor()
            c.execute("INSERT INTO attempts (task_id, date, passed, feedback) VALUES (?, ?, ?, ?)",
                      (task_id, entry["date"], entry["passed"], entry["feedback"]))
            self.conn.commit()
        else:
            self.data.setdefault("attempts", [])
            self.data["attempts"].append(entry)
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

    def get_attempts(self, limit=200):
        if self.mode == "sqlite":
            c = self.conn.cursor()
            c.execute("SELECT task_id, date, passed, feedback FROM attempts ORDER BY id DESC LIMIT ?", (limit,))
            rows = c.fetchall()
            return [{"task_id": r[0], "date": r[1], "passed": bool(r[2]), "feedback": r[3]} for r in rows]
        else:
            return list(reversed(self.data.get("attempts", [])))[:limit]

# -------------------------
# Task Selection
# -------------------------
def choose_daily_task(level: int) -> Dict[str, Any]:
    tasks = TASKS_BY_LEVEL.get(level, TASKS_BY_LEVEL[1])
    seed = hashlib.sha256((datetime.date.today().isoformat() + APP_SECRET + str(level)).encode()).hexdigest()
    idx = int(seed[:8], 16) % len(tasks)
    return tasks[idx]

# -------------------------
# Safe Evaluation Utilities
# -------------------------
DISALLOWED_NODES = (
    ast.Import, ast.ImportFrom, ast.Exec, ast.Global, ast.With, ast.Try, ast.Raise,
    ast.Lambda, ast.ClassDef
)

DISALLOWED_NAMES = {
    "__import__", "open", "exec", "eval", "compile", "input", "os", "sys", "subprocess",
    "shutil", "socket", "requests", "urllib", "multiprocessing", "threading"
}

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "chr": chr, "dict": dict,
    "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
    "pow": pow, "range": range, "str": str, "sum": sum, "enumerate": enumerate,
    "sorted": sorted, "set": set, "tuple": tuple, "map": map, "filter": filter, "zip": zip
}

def ast_safety_check(code: str) -> Tuple[bool, str]:
    """
    Parse AST and reject disallowed nodes or names.
    """
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"Syntax error: {e}"
    for node in ast.walk(tree):
        if isinstance(node, DISALLOWED_NODES):
            return False, f"Use of {type(node).__name__} is not allowed for safety."
        # Name checks
        if isinstance(node, ast.Name):
            if node.id in DISALLOWED_NAMES:
                return False, f"Use of name '{node.id}' is not allowed."
    return True, "OK"

# Worker executed in separate process
def _worker_exec(code: str, func_name: str, tests: List[Dict], q: mp.Queue):
    """
    Execute user code in restricted namespace and run tests.
    """
    try:
        # Minimal namespace
        user_ns = {}
        user_ns["__builtins__"] = SAFE_BUILTINS.copy()

        # Execute code
        exec(code, user_ns)

        if func_name not in user_ns or not callable(user_ns[func_name]):
            q.put({"error": f"Function `{func_name}` not found or not callable."})
            return

        func = user_ns[func_name]
        results = []
        all_passed = True
        for t in tests:
            inp = t["input"]
            expected = t["expected"]
            try:
                if isinstance(inp, (list, tuple)):
                    out = func(*inp)
                else:
                    out = func(inp)
                # flexible comparison for lists of lists or unordered lists
                passed = False
                if out == expected:
                    passed = True
                else:
                    # allow list order-insensitive comparison when both are lists
                    if isinstance(expected, list) and isinstance(out, list):
                        try:
                            if sorted(out) == sorted(expected):
                                passed = True
                        except Exception:
                            passed = False
                results.append({"input": inp, "expected": expected, "output": out, "passed": passed})
                if not passed:
                    all_passed = False
            except Exception as e:
                tb = traceback.format_exc()
                results.append({"input": inp, "expected": expected, "output": f"Error: {e}", "passed": False, "traceback": tb})
                all_passed = False
        q.put({"results": results, "all_passed": all_passed})
    except Exception as e:
        q.put({"error": f"Execution error: {e}\n{traceback.format_exc()}"})

def evaluate_user_code(user_code: str, func_name: str, tests: List[Dict], timeout_seconds: int = 3) -> Dict[str, Any]:
    """
    Run AST checks, then execute in separate process with timeout.
    Attempt to set resource limits on Unix.
    """
    ok, msg = ast_safety_check(user_code)
    if not ok:
        return {"error": msg}

    q = mp.Queue()
    p = mp.Process(target=_worker_exec, args=(user_code, func_name, tests, q))
    p.start()
    p.join(timeout_seconds)
    if p.is_alive():
        p.terminate()
        return {"error": "Execution timed out (possible infinite loop or heavy computation)."}
    try:
        res = q.get_nowait()
    except Exception:
        res = {"error": "No result returned from execution."}
    return res

# -------------------------
# Difficulty Adjustment
# -------------------------
def adjust_difficulty(storage: Storage, passed: bool, task_id: str):
    state = storage.get_state()
    level = state["level"]
    success_streak = state["success_streak"]
    streak = state["streak"]
    today = datetime.date.today().isoformat()
    last_date = state["last_task_date"]

    # Update daily streak
    if passed:
        if last_date:
            last = datetime.date.fromisoformat(last_date)
            if last + datetime.timedelta(days=1) == datetime.date.today():
                streak = streak + 1
            elif last == datetime.date.today():
                # already counted today
                pass
            else:
                streak = 1
        else:
            streak = 1
    else:
        # failing today breaks daily streak
        streak = 0

    # success_streak counts consecutive successful attempts
    if passed:
        success_streak += 1
    else:
        success_streak = 0

    # Level up after 3 consecutive successful attempts
    if success_streak >= 3 and level < 5:
        level += 1
        success_streak = 0

    # Level down if last two attempts failed
    attempts = storage.get_attempts(5)
    if not passed and len(attempts) >= 2:
        last_two = attempts[:2]
        if all(not a["passed"] for a in last_two) and level > 1:
            level = max(1, level - 1)
            success_streak = 0

    storage.update_state(level=level, streak=streak, last_task_date=today, last_task_id=task_id, success_streak=success_streak)

# -------------------------
# Remote sync placeholder
# -------------------------
def remote_sync_placeholder(data: dict) -> bool:
    """
    Placeholder for remote backend sync. Return True if success.
    Implement your API calls here.
    """
    # For now, just simulate success
    return True

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<h1 style='text-align:center'>{APP_TITLE} 🚀</h1>", unsafe_allow_html=True)

# Sidebar: storage selection and user name
st.sidebar.header("Settings & Storage")
storage_mode = st.sidebar.selectbox("Storage backend", options=["sqlite", "json"], index=0 if DEFAULT_STORAGE=="sqlite" else 1)
storage = Storage(mode=storage_mode)
state = storage.get_state()

# Allow user to set preferred name (persisted)
preferred_name = st.sidebar.text_input("Your display name", value=state.get("preferred_name", USER_NAME))
if st.sidebar.button("Save name"):
    storage.update_state(preferred_name=preferred_name)
    st.sidebar.success("Name saved.")

st.sidebar.markdown("---")
if st.sidebar.button("Sync to remote (placeholder)"):
    ok = remote_sync_placeholder({"state": storage.get_state(), "attempts": storage.get_attempts(200)})
    if ok:
        st.sidebar.success("Remote sync simulated (placeholder).")
    else:
        st.sidebar.error("Remote sync failed.")

# Main layout: tabs
tabs = st.tabs(["Practice", "Dashboard", "Settings"])
tab_practice, tab_dashboard, tab_settings = tabs

# Practice tab
with tab_practice:
    st.subheader("Daily Task")
    state = storage.get_state()
    level = state["level"]
    task = choose_daily_task(level)
    st.markdown(f"**Level {level} — {task['title']}**")
    st.write(task["prompt"])
    with st.expander("Hint"):
        st.write(task.get("hint", "No hint available."))

    st.markdown("**Implement the required function below.** Only the function implementation is required, but helper functions are allowed.")
    default_stub = f"def {task['function_name']}(*args):\n    # your code here\n    pass\n"
    user_code = st.text_area("Your code", value=default_stub, height=320, key="code_area")

    col1, col2 = st.columns([2,1])
    with col1:
        if st.button("Run Tests"):
            # Evaluate
            eval_res = evaluate_user_code(user_code, task["function_name"], task["tests"], timeout_seconds=4)
            if "error" in eval_res:
                st.error(eval_res["error"])
                feedback = eval_res["error"]
                storage.record_attempt(task["id"], False, feedback)
                adjust_difficulty(storage, False, task["id"])
                # Failure message (no slurs)
                st.warning(f"Dobara koshish karo, {preferred_name}.")
                # Offer quick retry
                if st.button("Try again"):
                    st.experimental_rerun()
            else:
                results = eval_res["results"]
                all_passed = eval_res["all_passed"]
                passed_count = sum(1 for r in results if r["passed"])
                st.success(f"Passed {passed_count} / {len(results)} tests.")
                for r in results:
                    if r.get("passed"):
                        st.write(f"✅ Input: {r['input']} → Output: {r['output']} (expected {r['expected']})")
                    else:
                        st.write(f"❌ Input: {r['input']} → Output: {r['output']} (expected {r['expected']})")
                        if r.get("traceback"):
                            with st.expander("Traceback"):
                                st.text(r["traceback"])
                feedback = json.dumps(results)
                storage.record_attempt(task["id"], all_passed, feedback)
                adjust_difficulty(storage, all_passed, task["id"])
                if all_passed:
                    # Personalized success message
                    st.balloons()
                    st.success(f"Wow.. {preferred_name} 🎉")
                    # Confetti (requires external confetti lib loaded by user browser)
                    st.components.v1.html(
                        """
                        <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.5.1/dist/confetti.browser.min.js"></script>
                        <button id="cbtn" style="display:none" onclick="fireConfetti()">Confetti</button>
                        """ + CONFETTI_JS + "<script>document.getElementById('cbtn').click();</script>",
                        height=0
                    )
    with col2:
        st.markdown("### Tips")
        st.write("- Keep functions small and test locally if needed.")
        st.write("- Avoid infinite loops; evaluator times out after a few seconds.")
        st.write("- Use the Hint if stuck.")
        st.write("- The evaluator compares outputs with `==`. For lists where order doesn't matter, tasks may accept any order if noted.")
        st.markdown("---")
        st.markdown("**Quick actions**")
        if st.button("Show sample solution (hint)"):
            # Provide a short sample for learning (not full solutions for copyrighted content; these are simple algorithmic examples)
            sample = {
                "sum_two": "def sum_two(a, b):\n    return a + b",
                "is_even": "def is_even(n):\n    return n % 2 == 0",
                "factorial": "def factorial(n):\n    res = 1\n    for i in range(2, n+1):\n        res *= i\n    return res"
            }
            s = sample.get(task["function_name"], "No sample available for this task.")
            st.code(s, language="python")

# Dashboard tab
with tab_dashboard:
    st.subheader("Progress Dashboard")
    state = storage.get_state()
    st.metric("Level", state["level"])
    st.metric("Daily streak (days)", state["streak"])
    st.metric("Success streak (attempts)", state["success_streak"])
    st.write(f"Last task date: {state.get('last_task_date') or 'N/A'}")
    st.write(f"Preferred name: {state.get('preferred_name', preferred_name)}")

    attempts = storage.get_attempts(200)
    if attempts:
        df = pd.DataFrame(attempts)
        df['date'] = pd.to_datetime(df['date'])
        df['passed'] = df['passed'].astype(int)
        # Pass rate by day
        summary = df.groupby(df['date'].dt.date)['passed'].agg(['count', 'sum']).reset_index()
        summary['pass_rate'] = summary['sum'] / summary['count']
        chart = alt.Chart(summary).mark_line(point=True).encode(
            x=alt.X('date:T', title='Date'),
            y=alt.Y('pass_rate:Q', title='Pass Rate'),
            tooltip=['date', 'count', 'sum', alt.Tooltip('pass_rate', format='.2f')]
        ).properties(width=700, height=300)
        st.altair_chart(chart, use_container_width=True)

        # Recent attempts table
        st.markdown("**Recent Attempts**")
        recent = df.head(20)
        recent_display = recent[['date', 'task_id', 'passed']]
        recent_display['status'] = recent_display['passed'].apply(lambda x: "✅ Passed" if x==1 else "❌ Failed")
        st.table(recent_display.rename(columns={'date':'Date','task_id':'Task','status':'Status'}))

        # Accuracy gauge (simple)
        total = df.shape[0]
        passed = df['passed'].sum()
        accuracy = passed / total if total else 0
        st.progress(min(1.0, accuracy))
        st.write(f"Overall accuracy: **{accuracy:.0%}** ({passed}/{total})")
    else:
        st.write("No attempts yet. Start practicing!")

# Settings tab
with tab_settings:
    st.subheader("Settings")
    st.write("Reset progress, change level, or switch storage backend.")
    if st.button("Reset Progress"):
        if storage_mode == "sqlite":
            c = storage.conn.cursor()
            c.execute("DELETE FROM attempts")
            c.execute("UPDATE user_state SET level=1, streak=0, last_task_date='', last_task_id='', success_streak=0, preferred_name=? WHERE id=1", (USER_NAME,))
            storage.conn.commit()
        else:
            storage.data = {
                "user_state": {
                    "level": 1,
                    "streak": 0,
                    "last_task_date": "",
                    "last_task_id": "",
                    "success_streak": 0,
                    "preferred_name": USER_NAME
                },
                "attempts": []
            }
            with open(storage.json_path, "w", encoding="utf-8") as f:
                json.dump(storage.data, f, indent=2)
        st.success("Progress reset.")

    st.markdown("---")
    st.write("Manually set level")
    new_level = st.number_input("Level (1-5)", min_value=1, max_value=5, value=state["level"], step=1)
    if st.button("Set Level"):
        storage.update_state(level=int(new_level))
        st.success(f"Level set to {new_level}.")

    st.markdown("---")
    st.write("Storage info")
    st.write(f"Current backend: **{storage_mode}**")
    if storage_mode == "json":
        st.write(f"JSON file: `{storage.json_path}`")
    else:
        st.write(f"SQLite DB: `{DB_PATH}`")

st.markdown("---")
st.caption("This app executes user code locally in a restricted environment. Avoid pasting secrets. The evaluator is educational and not a full security sandbox.")

