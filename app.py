"""Python Practice Studio - a Streamlit-based Python practice app."""
from __future__ import annotations

import ast
import builtins
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import queue
import sqlite3
import traceback
from typing import Any, Dict, List, Tuple

import altair as alt
import pandas as pd
import streamlit as st

APP_TITLE = "Python Practice Studio"
DB_PATH = "practice.db"
JSON_PATH = "practice.json"
USER_NAME = "Adnan Chotiya"
DEFAULT_STORAGE = "sqlite"
APP_SECRET = "streamlit_practice_tool_v2"

TASKS_BY_LEVEL: Dict[int, List[Dict[str, Any]]] = {
    1: [
        {"id":"l1_sum_two","title":"Sum Two Numbers","prompt":"Write `sum_two(a, b)` that returns the sum of two numbers.","function_name":"sum_two","tests":[{"input":[1,2],"expected":3},{"input":[-1,5],"expected":4},{"input":[0,0],"expected":0}],"hint":"Return a + b."},
        {"id":"l1_is_even","title":"Is Even","prompt":"Write `is_even(n)` that returns True if n is even, else False.","function_name":"is_even","tests":[{"input":[2],"expected":True},{"input":[3],"expected":False},{"input":[0],"expected":True}],"hint":"Use n % 2 == 0."}],
    2: [
        {"id":"l2_factorial","title":"Factorial","prompt":"Write `factorial(n)` returning n! for n >= 0.","function_name":"factorial","tests":[{"input":[0],"expected":1},{"input":[5],"expected":120},{"input":[3],"expected":6}],"hint":"Use a loop or recursion."},
        {"id":"l2_fib_n","title":"Nth Fibonacci","prompt":"Write `fib(n)` returning nth Fibonacci (0-indexed).","function_name":"fib","tests":[{"input":[0],"expected":0},{"input":[1],"expected":1},{"input":[7],"expected":13}],"hint":"An iterative approach is safe."}],
    3: [
        {"id":"l3_unique_words","title":"Unique Words","prompt":"Write `unique_words(s)` returning sorted unique lowercase words.","function_name":"unique_words","tests":[{"input":["Hello hello world"],"expected":["hello","world"]},{"input":["a b a c"],"expected":["a","b","c"]}],"hint":"Use set and sorted."},
        {"id":"l3_is_palindrome","title":"Is Palindrome","prompt":"Write `is_palindrome(s)` ignoring non-alphanumeric characters and case.","function_name":"is_palindrome","tests":[{"input":["A man, a plan, a canal: Panama"],"expected":True},{"input":["hello"],"expected":False}],"hint":"Filter characters and compare with the reverse."}],
    4: [
        {"id":"l4_group_anagrams","title":"Group Anagrams","prompt":"Write `group_anagrams(words)` grouping anagrams.","function_name":"group_anagrams","tests":[{"input":[["eat","tea","tan","ate","nat","bat"]],"expected":[["eat","tea","ate"],["tan","nat"],["bat"]]}],"hint":"Use the sorted word as a dictionary key."},
        {"id":"l4_two_sum","title":"Two Sum Indices","prompt":"Write `two_sum(nums, target)` returning two indices or None.","function_name":"two_sum","tests":[{"input":[[2,7,11,15],9],"expected":(0,1)},{"input":[[3,2,4],6],"expected":(1,2)}],"hint":"Use a dictionary to map values to indices."}],
    5: [
        {"id":"l5_merge_intervals","title":"Merge Intervals","prompt":"Write `merge_intervals(intervals)` merging overlapping intervals.","function_name":"merge_intervals","tests":[{"input":[[[1,3],[2,6],[8,10],[15,18]]],"expected":[[1,6],[8,10],[15,18]]},{"input":[[[1,4],[4,5]]],"expected":[[1,5]]}],"hint":"Sort by start and merge."},
        {"id":"l5_longest_substring","title":"Longest Substring Without Repeating","prompt":"Write `length_of_longest_substring(s)` returning the longest non-repeating substring length.","function_name":"length_of_longest_substring","tests":[{"input":["abcabcbb"],"expected":3},{"input":["bbbbb"],"expected":1}],"hint":"Use a sliding window."}],
}


def default_state() -> Dict[str, Any]:
    return {"level":1,"streak":0,"last_task_date":"","last_task_id":"","success_streak":0,"preferred_name":USER_NAME}


def init_sqlite(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS user_state (id INTEGER PRIMARY KEY, level INTEGER, streak INTEGER, last_task_date TEXT, last_task_id TEXT, success_streak INTEGER, preferred_name TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, date TEXT, passed INTEGER, feedback TEXT)")
    if conn.execute("SELECT COUNT(*) FROM user_state").fetchone()[0] == 0:
        s = default_state()
        conn.execute("INSERT INTO user_state VALUES (1,?,?,?,?,?,?)", tuple(s.values()))
    conn.commit()
    return conn


def init_json(path: str = JSON_PATH) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("user_state", default_state())
        data.setdefault("attempts", [])
        return data
    except (OSError, json.JSONDecodeError):
        data = {"user_state":default_state(),"attempts":[]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data


class Storage:
    def __init__(self, mode: str = DEFAULT_STORAGE):
        self.mode = mode if mode in {"sqlite", "json"} else DEFAULT_STORAGE
        if self.mode == "sqlite":
            self.conn = init_sqlite()
        else:
            self.json_path, self.data = JSON_PATH, init_json()

    def get_state(self) -> Dict[str, Any]:
        if self.mode == "sqlite":
            row = self.conn.execute("SELECT level,streak,last_task_date,last_task_id,success_streak,preferred_name FROM user_state WHERE id=1").fetchone()
            return dict(zip(("level","streak","last_task_date","last_task_id","success_streak","preferred_name"), row)) if row else default_state()
        return dict(self.data.get("user_state", default_state()))

    def save_json(self) -> None:
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def update_state(self, **changes: Any) -> None:
        state = default_state(); state.update(self.get_state()); state.update(changes)
        if self.mode == "sqlite":
            self.conn.execute("UPDATE user_state SET level=?,streak=?,last_task_date=?,last_task_id=?,success_streak=?,preferred_name=? WHERE id=1", tuple(state[k] for k in ("level","streak","last_task_date","last_task_id","success_streak","preferred_name")))
            self.conn.commit()
        else:
            self.data["user_state"] = state; self.save_json()

    def record_attempt(self, task_id: str, passed: bool, feedback: str) -> None:
        date = dt.date.today().isoformat()
        if self.mode == "sqlite":
            self.conn.execute("INSERT INTO attempts(task_id,date,passed,feedback) VALUES(?,?,?,?)", (task_id,date,int(passed),feedback)); self.conn.commit()
        else:
            self.data.setdefault("attempts", []).append({"task_id":task_id,"date":date,"passed":bool(passed),"feedback":feedback}); self.save_json()

    def get_attempts(self, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, int(limit))
        if self.mode == "sqlite":
            rows = self.conn.execute("SELECT task_id,date,passed,feedback FROM attempts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [{"task_id":r[0],"date":r[1],"passed":bool(r[2]),"feedback":r[3]} for r in rows]
        return list(reversed(self.data.get("attempts", [])))[:limit]


def choose_daily_task(level: int) -> Dict[str, Any]:
    tasks = TASKS_BY_LEVEL.get(int(level), TASKS_BY_LEVEL[1])
    seed = hashlib.sha256(f"{dt.date.today()}{APP_SECRET}{level}".encode()).hexdigest()
    return tasks[int(seed[:8], 16) % len(tasks)]


_NODE_NAMES = ("Import","ImportFrom","Global","Nonlocal","With","AsyncWith","Try","TryStar","Raise","Lambda","ClassDef","AsyncFunctionDef")
DISALLOWED_NODES = tuple(getattr(ast, name) for name in _NODE_NAMES if hasattr(ast, name))
DISALLOWED_NAMES = {"__import__","open","exec","eval","compile","input","breakpoint","os","sys","subprocess","shutil","socket","requests","urllib","multiprocessing","threading"}
SAFE_BUILTINS = {name: getattr(builtins, name) for name in ("abs","all","any","bool","chr","dict","float","int","len","list","max","min","pow","range","str","sum","enumerate","sorted","set","tuple","map","filter","zip","isinstance")}
SAFE_BUILTINS.update({"Exception":Exception,"ValueError":ValueError,"TypeError":TypeError})


def ast_safety_check(code: str) -> Tuple[bool, str]:
    try:
        tree = ast.parse(code, mode="exec")
    except (SyntaxError, ValueError, TypeError) as exc:
        return False, f"Syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, DISALLOWED_NODES): return False, f"Use of {type(node).__name__} is not allowed."
        if isinstance(node, ast.Name) and node.id in DISALLOWED_NAMES: return False, f"Use of name '{node.id}' is not allowed."
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"): return False, "Dunder attribute access is not allowed."
    return True, "OK"


def equal_output(actual: Any, expected: Any) -> bool:
    if actual == expected: return True
    if isinstance(actual, list) and isinstance(expected, list):
        try: return sorted(actual, key=repr) == sorted(expected, key=repr)
        except (TypeError, ValueError): return False
    return False


def worker(code: str, name: str, tests: List[Dict[str, Any]], result_queue: Any) -> None:
    try:
        namespace = {"__builtins__": SAFE_BUILTINS.copy()}
        exec(compile(code, "<student_code>", "exec"), namespace, namespace)
        func = namespace.get(name)
        if not callable(func): result_queue.put({"error":f"Function `{name}` not found or not callable."}); return
        results=[]; all_passed=True
        for test in tests:
            try:
                inp, expected = test["input"], test["expected"]
                output = func(*inp) if isinstance(inp,(list,tuple)) else func(inp)
                passed = equal_output(output, expected); item={"input":inp,"expected":expected,"output":output,"passed":passed}
            except Exception as exc:
                passed=False; item={"input":test.get("input"),"expected":test.get("expected"),"output":f"Error: {exc}","passed":False,"traceback":traceback.format_exc()}
            results.append(item); all_passed = all_passed and passed
        result_queue.put({"results":results,"all_passed":all_passed})
    except Exception as exc: result_queue.put({"error":f"Execution error: {exc}\n{traceback.format_exc()}"})


def evaluate_user_code(code: str, name: str, tests: List[Dict[str, Any]], timeout_seconds: float = 4) -> Dict[str, Any]:
    ok, message = ast_safety_check(code)
    if not ok: return {"error":message}
    ctx = mp.get_context("spawn"); result_queue=ctx.Queue(); process=ctx.Process(target=worker,args=(code,name,tests,result_queue))
    try:
        process.start(); process.join(timeout_seconds)
        if process.is_alive(): process.terminate(); process.join(1); return {"error":"Execution timed out."}
        try: return result_queue.get(timeout=.5)
        except queue.Empty: return {"error":"No result returned from execution."}
    except (OSError, RuntimeError) as exc: return {"error":f"Could not start evaluator: {exc}"}
    finally: result_queue.close(); result_queue.join_thread()


def adjust_difficulty(storage: Storage, passed: bool, task_id: str) -> None:
    state=storage.get_state(); today=dt.date.today(); level=int(state["level"]); success=int(state["success_streak"]); streak=int(state["streak"])
    if passed:
        try:
            previous=dt.date.fromisoformat(state.get("last_task_date", "")); streak=streak+1 if previous==today-dt.timedelta(days=1) else (streak if previous==today else 1)
        except ValueError: streak=1
        success += 1
    else: streak=success=0
    if success >= 3 and level < 5: level += 1; success=0
    recent=storage.get_attempts(2)
    if not passed and level > 1 and len(recent)==2 and all(not item["passed"] for item in recent): level -= 1
    storage.update_state(level=level,streak=streak,last_task_date=today.isoformat(),last_task_id=task_id,success_streak=success)


def reset_progress(storage: Storage) -> None:
    if storage.mode == "sqlite":
        storage.conn.execute("DELETE FROM attempts"); s=default_state(); storage.conn.execute("UPDATE user_state SET level=?,streak=?,last_task_date=?,last_task_id=?,success_streak=?,preferred_name=? WHERE id=1", tuple(s.values())); storage.conn.commit()
    else: storage.data={"user_state":default_state(),"attempts":[]}; storage.save_json()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
    st.title(f"{APP_TITLE} 🚀")
    st.sidebar.header("Settings & Storage")
    mode=st.sidebar.selectbox("Storage backend", ["sqlite","json"], index=0 if DEFAULT_STORAGE=="sqlite" else 1); storage=Storage(mode); state=storage.get_state()
    name=st.sidebar.text_input("Your display name", value=state.get("preferred_name") or USER_NAME)
    if st.sidebar.button("Save name"): storage.update_state(preferred_name=name.strip() or USER_NAME); st.sidebar.success("Name saved.")
    practice,dashboard,settings=st.tabs(["Practice","Dashboard","Settings"])
    with practice:
        state=storage.get_state(); task=choose_daily_task(state["level"]); st.subheader("Daily Task"); st.write(f"**Level {state['level']} — {task['title']}**"); st.write(task["prompt"])
        with st.expander("Hint"): st.write(task["hint"])
        stub=f"def {task['function_name']}(*args):\n    # your code here\n    pass\n"; code=st.text_area("Your code",stub,height=300,key="code_area")
        if st.button("Run Tests", type="primary"):
            result=evaluate_user_code(code,task["function_name"],task["tests"])
            if "error" in result:
                st.error(result["error"]); storage.record_attempt(task["id"],False,result["error"]); adjust_difficulty(storage,False,task["id"]); st.warning(f"Dobara koshish karo, {name}.")
            else:
                for item in result["results"]:
                    st.write(("✅" if item["passed"] else "❌") + f" Input: {item['input']} → Output: {item['output']} (expected {item['expected']})")
                passed=result["all_passed"]; st.success(f"Passed {sum(item['passed'] for item in result['results'])} / {len(result['results'])} tests."); storage.record_attempt(task["id"],passed,json.dumps(result["results"],default=repr)); adjust_difficulty(storage,passed,task["id"])
                if passed: st.balloons(); st.success(f"Wow, {name} 🎉")
    with dashboard:
        state=storage.get_state(); a,b,c=st.columns(3); a.metric("Level",state["level"]); b.metric("Daily streak",state["streak"]); c.metric("Success streak",state["success_streak"])
        attempts=storage.get_attempts()
        if attempts:
            frame=pd.DataFrame(attempts); frame["date"]=pd.to_datetime(frame["date"],errors="coerce"); frame["passed"]=frame["passed"].astype(bool); frame=frame.dropna(subset=["date"])
            summary=frame.groupby(frame["date"].dt.date)["passed"].agg(count="count",passed="sum").reset_index(); summary["pass_rate"]=summary["passed"]/summary["count"]
            chart=alt.Chart(summary).mark_line(point=True).encode(x=alt.X("date:T",title="Date"),y=alt.Y("pass_rate:Q",title="Pass Rate",scale=alt.Scale(domain=[0,1])),tooltip=["date","count","passed"]).properties(height=300); st.altair_chart(chart,use_container_width=True)
            st.dataframe(frame.head(20)[["date","task_id","passed"]],use_container_width=True,hide_index=True); st.progress(float(frame["passed"].mean()))
        else: st.write("No attempts yet. Start practicing!")
    with settings:
        if st.button("Reset Progress"): reset_progress(storage); st.success("Progress reset.")
        level=st.number_input("Level (1-5)",min_value=1,max_value=5,value=int(storage.get_state()["level"]),step=1)
        if st.button("Set Level"): storage.update_state(level=int(level)); st.success("Level updated.")
        st.write(f"Current backend: **{mode}**")
    st.caption("The evaluator is educational isolation, not a full security sandbox.")


if __name__ == "__main__":
    main()
