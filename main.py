import base64
import json
import streamlit as st
import pandas as pd
from streamlit.components.v1 import html as components_html
import re
import os
import urllib.request
import urllib.parse
import sys
import tempfile
import subprocess
import time
import webbrowser
import inspect
import socket


# Launcher: when run directly (or from a PyInstaller bundle), spawn a Streamlit server
# that serves this file and open the browser. The spawned process receives
# environment variable `LAUNCHED_BY_STREAMLIT=1` so the app doesn't re-spawn itself.
# This makes a packaged executable behave like "double-click to open app".
if getattr(sys, "frozen", False) and os.environ.get("LAUNCHED_BY_STREAMLIT") != "1":
    # Only perform the launcher behavior for frozen (PyInstaller) builds.
    try:
        # Determine a path to run with streamlit. Prefer the current .py file when available.
        src_path = None
        try:
            src_path = os.path.abspath(__file__)
        except Exception:
            src_path = None

        if src_path and src_path.endswith(".py"):
            run_path = src_path
        else:
            # Try to get source from the loaded module and write to a temp file
            try:
                src = inspect.getsource(sys.modules[__name__])
            except Exception:
                src = None

            if src:
                tf = tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8")
                tf.write(src)
                tf.flush()
                tf.close()
                run_path = tf.name
            else:
                run_path = None

        env = os.environ.copy()
        env["LAUNCHED_BY_STREAMLIT"] = "1"
        port = int(env.get("STREAMLIT_PORT", "8501"))

        # If the port is already serving, assume an existing Streamlit server is present; open browser and exit.
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                webbrowser.open(f"http://localhost:{port}")
                sys.exit(0)
        except Exception:
            # port not in use — continue to spawn
            pass

        if run_path:
            # Prefer running Streamlit in-process when possible (avoids subprocess and module resolution issues in frozen apps)
            try:
                import threading
                try:
                    from streamlit.web import cli as stcli
                except Exception:
                    stcli = None

                def start_streamlit_in_thread(path):
                    try:
                        old_argv = sys.argv
                        sys.argv = [old_argv[0], "run", path, "--server.port", str(port), "--server.headless", "true"]
                        try:
                            if stcli is not None:
                                stcli.main()
                            else:
                                # fallback to subprocess inside thread
                                subprocess.run([sys.executable, "-m", "streamlit", "run", path, "--server.port", str(port), "--server.headless", "true"], env=env)
                        finally:
                            sys.argv = old_argv
                    except Exception:
                        pass

                # Start Streamlit server in background thread so we can run GUI on main thread
                t = threading.Thread(target=start_streamlit_in_thread, args=(run_path,), daemon=True)
                t.start()

                # Wait for the server to be ready (poll) before opening UI to avoid blank webview
                server_ready = False
                wait_start = time.time()
                timeout = float(env.get("LAUNCHER_WAIT_TIMEOUT", 15.0))
                while time.time() - wait_start < timeout:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=1):
                            server_ready = True
                            break
                    except Exception:
                        time.sleep(0.5)

                # Try to open in native window via pywebview if available and server is ready,
                # otherwise open system browser once ready. If server never became ready, open browser anyway.
                try:
                    import webview
                except Exception:
                    webview = None

                if server_ready:
                    try:
                        if webview is not None:
                            win = webview.create_window("Student Dashboard", f"http://localhost:{port}", width=1100, height=800)
                            webview.start()
                            sys.exit(0)
                        else:
                            webbrowser.open(f"http://localhost:{port}")
                    except Exception:
                        try:
                            webbrowser.open(f"http://localhost:{port}")
                        except Exception:
                            pass
                else:
                    # Server did not appear; open browser anyway in case it comes up later
                    try:
                        webbrowser.open(f"http://localhost:{port}")
                    except Exception:
                        pass

                # If the thread is running, exit the launcher process to leave server running
                if t.is_alive():
                    sys.exit(0)
            except Exception:
                # If any error occurs, fall through and allow normal execution
                pass
    except Exception:
        # If anything goes wrong, continue running — streamlit CLI may have invoked us.
        pass



# App header (styled) + inject small CSS for contrast, colors, and icon nav styling
components_html(r"""
<div style='display:flex; align-items:baseline; justify-content:space-between; margin-bottom:12px'>
    <div>
        <h1 style='margin:0; font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; color:#0f172a;'>Academic Success Dashboard</h1>
        <div style='color:#475569; margin-top:4px'>Visualize courses, track GPA, and get improvement tips.</div>
    </div>
    <div style='color:#64748b; font-size:12px'>Your personal academic dashboard</div>
</div>
""", height=80)

components_html(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
/* Apply Inter (fallback to system fonts) globally */
html, body, .stApp, .main, .block-container, .streamlit-expanderHeader, .st-bk, .reportview-container { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial !important; color: #0b1220; }
.app-header { font-family: 'Inter', Arial, sans-serif !important; }
.dashboard-card { position:relative; background: linear-gradient(180deg,#ffffff,#fbfdff); border-radius:12px; padding:14px 14px 14px 22px; margin:10px 0; box-shadow: 0 6px 18px rgba(11,17,32,0.06); transition: transform .12s ease, box-shadow .12s ease; border: 1px solid #e6edf3; }
.dashboard-card:hover { transform: translateY(-4px); box-shadow: 0 12px 30px rgba(11,17,32,0.10); }
.course-name { font-weight:700; color:#0b1220; }
.grade-badge { display:inline-block; padding:6px 10px; border-radius:999px; color:#fff; font-weight:700; }
.badge-good { background:#166534; }
.badge-bad { background:#b91c1c; }
.nav-icon { font-size:20px; padding:8px 12px; margin:4px; border-radius:8px; cursor:pointer; }
.nav-icon.selected { background:#f5f5f5; color:#0b1220; }
table.course-table { width:100%; border-collapse:collapse; }
table.course-table th, table.course-table td { padding:8px 6px; text-align:left; border-bottom:1px solid #cbd5e1; }
.stButton>button { border-radius:10px; padding:8px 10px; }
</style>
""", height=0)

# --- Quick templates and page navigation ---
# Number of course rows is managed in the Edit Courses page and stored in session_state

# (Quick templates removed per request)

# Cookie helpers (encode/decode JSON to base64)
COOKIE_NAME = "student_dashboard_data"

def encode_data_for_cookie(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

def decode_data_from_cookie(b64):
    try:
        return json.loads(base64.urlsafe_b64decode(b64.encode()).decode())
    except Exception:
        return None

def inject_read_cookie_on_load(cookie_name=COOKIE_NAME):
        # If query param `data` is missing, read cookie and set it into query string to pass it to Streamlit on reload
        js = rf"""
        <script>
        (function() {{
            function getCookie(n) {{
                const v = document.cookie.match('(^|;)\\s*' + n + '\\s*=\\s*([^;]+)');
                return v ? v.pop() : null;
            }}
            const params = new URLSearchParams(window.location.search);
            if (!params.has('data')) {{
                const c = getCookie('{COOKIE_NAME}');
                if (c) {{
                    params.set('data', c);
                    window.location.search = params.toString();
                }}
            }}
        }})();
        </script>
        """
        components_html(js, height=0)

def inject_set_cookie_and_reload(data_b64, cookie_name=COOKIE_NAME):
    days = st.session_state.get("cookie_ttl", 365)
    js = rf"""
    <script>
    (function(){{
      var d = new Date(); d.setTime(d.getTime() + ({days}*24*60*60*1000));
      document.cookie = '{COOKIE_NAME}=' + '{data_b64}' + ';expires=' + d.toUTCString() + ';path=/';
      // reload without data param so the read-on-load picks cookie
      window.location = window.location.pathname;
    }})();
    </script>
    """
    components_html(js, height=0)

def inject_clear_cookie_and_reload(cookie_name=COOKIE_NAME):
    js = rf"""
    <script>
    (function(){{
        document.cookie = '{COOKIE_NAME}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/';
        window.location = window.location.pathname;
    }})();
    </script>
    """
    components_html(js, height=0)


def safe_rerun():
    """Compatibility wrapper for Streamlit rerun across versions.
    Tries to call `st.experimental_rerun()` if present. If not available,
    attempt to raise Streamlit's internal RerunException. As a last resort,
    call `st.stop()` to halt execution (changes to session state will persist).
    """
    try:
        # Preferred API when available
        st.experimental_rerun()
        return
    except Exception:
        pass
    # Try internal RerunException paths used by different Streamlit versions
    try:
        from streamlit.runtime.scriptrunner.script_runner import RerunException
        raise RerunException()
    except Exception:
        try:
            # Older/alternate import path
            from streamlit.script_runner import RerunException as RerunException2
            raise RerunException2()
        except Exception:
            # Fallback: stop execution gracefully
            try:
                st.stop()
            except Exception:
                # If even st.stop() isn't available, raise a generic exception
                raise RuntimeError("Could not trigger Streamlit rerun or stop")

# Breakdown parser (moved up so Edit Courses can auto-import)
def parse_breakdown_lines(raw):
    comps = []
    if not raw:
        return comps
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r'[:;,]', line)
        if len(parts) >= 3:
            name = parts[0].strip()
            try:
                weight = float(parts[1].strip())
                grade = float(parts[2].strip())
            except Exception:
                continue
            comps.append({"name": name, "weight": weight, "grade": grade})
    return comps

# Attempt to load data from query param (populated by cookie-read JS) or show read-cookie injector
loaded_from_cookie = False
params = st.query_params
initial_courses = None
if "data" in params:
    parsed = decode_data_from_cookie(params.get("data")[0])
    if parsed and isinstance(parsed, dict) and parsed.get("courses"):
        initial_courses = parsed["courses"]
        loaded_from_cookie = True
else:
    inject_read_cookie_on_load()

# If cookie provided initial courses, populate session_state defaults (do not overwrite existing values)
if initial_courses:
    for i, c in enumerate(initial_courses):
        if f"name_{i}" not in st.session_state:
            st.session_state[f"name_{i}"] = c.get("name", "")
        if f"credits_{i}" not in st.session_state:
            st.session_state[f"credits_{i}"] = int(c.get("credits", 0))
        if f"grade_{i}" not in st.session_state:
            st.session_state[f"grade_{i}"] = float(c.get("grade", 0.0))
        # keep raw breakdown for reference (not auto-parsed)
        if f"breakdown_raw_{i}" not in st.session_state:
            st.session_state[f"breakdown_raw_{i}"] = c.get("breakdown_raw", "")

# default rows if not set
default_rows = max(1, len(initial_courses) if initial_courses else 3)
if "rows" not in st.session_state:
    st.session_state["rows"] = default_rows

# Sidebar page navigation as icon buttons
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"

st.sidebar.markdown("#### Navigate")
if st.sidebar.button("📊 Dashboard"):
    st.session_state["page"] = "Dashboard"
if st.sidebar.button("✏️ Edit Courses"):
    st.session_state["page"] = "Edit Courses"
if st.sidebar.button("🔎 Deep Dive"):
    st.session_state["page"] = "Deep Dive"
if st.sidebar.button("⚙️ Settings"):
    st.session_state["page"] = "Settings"

page = st.session_state.get("page", "Dashboard")

if page == "Edit Courses":
    st.header("Edit Courses")
    rows = st.slider("Number of courses", min_value=1, max_value=12, step=1, value=st.session_state.get("rows", default_rows))
    st.session_state["rows"] = rows
    for i in range(rows):
        pre_name = st.session_state.get(f"name_{i}", "")
        pre_credits = st.session_state.get(f"credits_{i}", 0)
        pre_grade = st.session_state.get(f"grade_{i}", 0.0)
        pre_break_raw = st.session_state.get(f"breakdown_raw_{i}", "")
        with st.expander(f"Course {i+1}", expanded=(i == 0)):
            col_name, col_credits, col_grade = st.columns([3, 1, 1])
            # no quick templates — enter values manually or import via Settings

            course_name = col_name.text_input("Name", value=pre_name, key=f"name_{i}")
            course_credits = col_credits.number_input("Credits", min_value=0, max_value=10, step=1, value=int(pre_credits), key=f"credits_{i}")
            course_grade = col_grade.number_input("Expected GPA", min_value=0.00, max_value=4.33, step=0.01, format="%.2f", value=float(pre_grade), key=f"grade_{i}")

            st.markdown("**Grade breakdown** — add labeled components (label, weight, grade)")
            # Auto-import raw breakdown into structured components if available and no components set yet
            if pre_break_raw and (f"comp_count_{i}" not in st.session_state or st.session_state.get(f"comp_count_{i}", 0) == 0):
                parsed_comps = parse_breakdown_lines(pre_break_raw)
                if parsed_comps:
                    st.session_state[f"comp_count_{i}"] = len(parsed_comps)
                    for j, comp in enumerate(parsed_comps):
                        st.session_state[f"comp_name_{i}_{j}"] = comp.get("name", "")
                        st.session_state[f"comp_weight_{i}_{j}"] = comp.get("weight", 0.0)
                        st.session_state[f"comp_grade_{i}_{j}"] = comp.get("grade", 0.0)

            comp_count = st.number_input("Number of components", min_value=0, max_value=12, value=st.session_state.get(f"comp_count_{i}", 0), key=f"comp_count_{i}")
            if pre_break_raw:
                st.caption("Imported breakdown (read-only):")
                st.text_area("Imported breakdown", value=pre_break_raw, key=f"breakdown_raw_view_{i}")
            for j in range(int(comp_count)):
                c1, c2, c3 = st.columns([2, 1, 1])
                cname = c1.text_input("Component name", value=st.session_state.get(f"comp_name_{i}_{j}", ""), key=f"comp_name_{i}_{j}")
                cweight = c2.number_input("Weight", min_value=0.0, max_value=1000.0, step=0.1, value=float(st.session_state.get(f"comp_weight_{i}_{j}", 0.0)), key=f"comp_weight_{i}_{j}")
                cgrade = c3.number_input("Grade", min_value=0.0, max_value=4.33, step=0.01, format="%.2f", value=float(st.session_state.get(f"comp_grade_{i}_{j}", 0.0)), key=f"comp_grade_{i}_{j}")

# Build course_data from session_state so other pages can consume it
course_data = []
rows_current = st.session_state.get("rows", default_rows)
for i in range(rows_current):
    name = st.session_state.get(f"name_{i}", "")
    credits = st.session_state.get(f"credits_{i}", 0)
    grade = st.session_state.get(f"grade_{i}", 0.0)
    comp_count = st.session_state.get(f"comp_count_{i}", 0)
    comps = []
    for j in range(int(comp_count)):
        comps.append({
            "name": st.session_state.get(f"comp_name_{i}_{j}", ""),
            "weight": float(st.session_state.get(f"comp_weight_{i}_{j}", 0.0)),
            "grade": float(st.session_state.get(f"comp_grade_{i}_{j}", 0.0)),
        })
    # also include any imported raw breakdown for reference
    raw = st.session_state.get(f"breakdown_raw_{i}", "")
    course_data.append({"name": name, "credits": credits, "grade": grade, "components": comps, "breakdown_raw": raw})

courses_df = pd.DataFrame(course_data)

# --- Parse breakdowns and compute effective grades ---

effective_grades = []
parsed_breakdowns = []
for _, row in courses_df.iterrows():
    # Prefer structured components if provided
    comps = row.get("components") if isinstance(row.get("components"), list) and row.get("components") else None
    if not comps:
        # fallback to parsing raw breakdown text
        comps = parse_breakdown_lines(row.get("breakdown_raw", ""))
    parsed_breakdowns.append(comps or [])
    if comps:
        total_w = sum([abs(c["weight"]) for c in comps])
        if total_w > 0:
            weighted = sum([c["weight"] * c["grade"] for c in comps]) / total_w
            effective_grades.append(weighted)
        else:
            effective_grades.append(row.get("grade", 0.0))
    else:
        effective_grades.append(row.get("grade", 0.0))

courses_df["effective_grade"] = effective_grades


def run_local_llm(prompt, backend, model_path, max_tokens=150):
    """Run a local LLM backend. Returns (output, error_message).
    Tries gpt4all first if selected, then llama_cpp if selected.
    """
    if not backend:
        return None, "No backend selected"
    backend = backend.lower()
    if backend == "gpt4all":
        try:
            from gpt4all import GPT4All
        except Exception as e:
            return None, f"gpt4all import failed: {e}"
        try:
            # model_path may be a model name or path depending on gpt4all installation
            model = GPT4All(model_name=model_path or "")
            # many gpt4all wrappers provide .generate
            out = model.generate(prompt)
            if isinstance(out, (list, tuple)):
                out = out[0]
            return str(out), None
        except Exception as e:
            return None, str(e)
    elif backend == "llama_cpp":
        try:
            from llama_cpp import Llama
        except Exception as e:
            return None, f"llama_cpp import failed: {e}"
        try:
            llm = Llama(model_path=model_path)
            resp = llm.create(prompt=prompt, max_tokens=max_tokens)
            if isinstance(resp, dict) and resp.get("choices"):
                out = resp["choices"][0].get("text")
            else:
                out = str(resp)
            return out, None
        except Exception as e:
            return None, str(e)
    else:
        return None, f"Unknown backend: {backend}"


def download_model(url, dest_dir):
    """Download model from URL into dest_dir. Returns (dest_path, error_message)."""
    try:
        os.makedirs(dest_dir, exist_ok=True)
        filename = os.path.basename(urllib.parse.urlparse(url).path) or "model.bin"
        dest = os.path.join(dest_dir, filename)
        # simple download; urllib handles basic redirects
        urllib.request.urlretrieve(url, dest)
        return dest, None
    except Exception as e:
        return None, str(e)

# place dataframe and target GPA nicely on Dashboard
if page == "Dashboard":
    left, right = st.columns([3, 1])

    # Target input and summary column
    target_gpa = right.number_input("Target GPA", min_value=0.00, max_value=4.33, step=0.01, format="%.2f")
    right.markdown("---")

    # Pretty course cards using Streamlit elements (bubbly, rounded, friendly)
    if courses_df.empty:
        left.info("No courses yet — add some in Edit Courses.")
    else:
        # Display courses as responsive cards (2 per row)
        per_row = 2
        items = courses_df.reset_index().to_dict('records')
        for i in range(0, len(items), per_row):
            row_items = items[i:i+per_row]
            cols_row = left.columns(len(row_items))
            for col, item in zip(cols_row, row_items):
                name = item.get('name') or 'Unnamed'
                credits = int(item.get('credits', 0))
                eff = float(item.get('effective_grade', 0.0))
                pct = min(100.0, (eff / 4.33) * 100.0) if eff else 0.0
                with col:
                    col.markdown(
                        f"""
                        <div class='dashboard-card' style='padding-left:36px;'>
                            <div style='position:absolute; left:0; top:0; bottom:0; width:8px; border-radius:12px 0 0 12px; background: linear-gradient(180deg,#7c3aed,#06b6d4);'></div>
                            <div style='display:flex; justify-content:space-between; align-items:center; padding-bottom:8px; border-bottom:1px solid #eef2f6;'>
                                <div style='font-size:16px; font-weight:700;'>{name}</div>
                                <div style='color:#475569; font-size:13px;'>Credits: {credits}</div>
                            </div>
                            <div style='margin-top:10px; display:flex; align-items:center; gap:12px; padding-top:10px;'>
                                <div style='flex:1'>
                                    <div style='font-size:12px; color:#64748b;'>Effective GPA</div>
                                    <div style='font-size:22px; font-weight:800; color:#0b1220;'>{eff:.2f}</div>
                                </div>
                                <div style='width:140px'>
                                    <div style='height:12px; background:#f3f4f6; border-radius:999px; overflow:hidden;'>
                                        <div style='width:{pct:.1f}%; height:12px; background:#111827; border-radius:999px;'></div>
                                    </div>
                                    <div style='font-size:11px; color:#64748b; margin-top:6px'>{pct:.0f}% of 4.33</div>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if col.button("Deep Dive", key=f"deep_{item['index']}"):
                        st.session_state["page"] = "Deep Dive"
                        st.session_state["deep_dive_index"] = int(item['index'])
                        safe_rerun()

    # Risk analysis and improvement suggestions
    if courses_df.empty or courses_df["credits"].sum() == 0:
        st.info("Enter at least one course with credits > 0 to analyze risk.")
    else:
        total_credits = float(courses_df["credits"].sum())
        # use effective grade (from structured components or breakdown)
        current_qp = (courses_df["credits"] * courses_df["effective_grade"]).sum()
        current_gpa = current_qp / total_credits

        # Summary labels
        right.metric("Current GPA", f"{current_gpa:.2f}", delta=f"{(current_gpa - target_gpa):+.2f}")
        badge_class = "badge-good" if current_gpa >= target_gpa else "badge-bad"
        right.markdown(f"**Target GPA**: <span class='grade-badge {badge_class}'>{target_gpa:.2f}</span>", unsafe_allow_html=True)

        required_qp = target_gpa * total_credits
        deficit_qp = required_qp - current_qp

        if deficit_qp <= 0:
            st.success(f"On track — projected GPA meets/exceeds target by {(current_gpa - target_gpa):.2f}.")
        else:
            st.error(f"Shortfall: {deficit_qp:.2f} quality points needed to reach target.")

            # Compute maximum possible gain per course (if raised to 4.33)
            analysis = courses_df.copy()
            # use effective_grade as base for possible gains
            analysis["grade"] = analysis["effective_grade"]
            analysis["max_gain_qp"] = analysis["credits"] * (4.33 - analysis["grade"]).clip(lower=0)
            total_possible_gain = analysis["max_gain_qp"].sum()

            if total_possible_gain + 1e-9 < deficit_qp:
                st.warning("Even raising all courses to 4.33 will not reach the target.")
                st.write(f"Maximum possible extra quality points: {total_possible_gain:.2f}")
            else:
                # Greedy selection: bump courses with largest potential gain first
                analysis = analysis.sort_values("max_gain_qp", ascending=False)
                remaining = deficit_qp
                suggestions = []
                for _, row in analysis.iterrows():
                    if remaining <= 0:
                        break
                    if row["max_gain_qp"] <= 0:
                        continue
                    take_qp = min(row["max_gain_qp"], remaining)
                    needed_grade_increase = take_qp / row["credits"]
                    suggested_grade = min(row["grade"] + needed_grade_increase, 4.33)
                    suggestions.append(
                        {
                            "name": row["name"],
                            "credits": int(row["credits"]),
                            "current_grade": round(row["grade"], 2),
                            "suggested_grade": round(suggested_grade, 2),
                        }
                    )
                    remaining -= take_qp

                st.subheader("Suggested course bumps to hit target")
                st.table(pd.DataFrame(suggestions))

            # High-risk courses: high-credit courses below target
            credit_threshold = courses_df["credits"].quantile(0.66) if len(courses_df) > 1 else 0
            high_risk = courses_df[(courses_df["credits"] >= credit_threshold) & (courses_df["grade"] < target_gpa)]
            if not high_risk.empty:
                st.subheader("High-risk courses (high credit & below target)")
                st.table(high_risk[["name", "credits", "grade"]].assign(grade=lambda d: d["grade"].round(2)))
            else:
                st.write("No high-credit courses are below the target GPA.")

        # Visual: course grades vs target
        st.subheader("Course grades vs target")
        viz = courses_df[["name", "effective_grade"]].copy()
        viz = viz.set_index("name")["effective_grade"].rename("grade")
        st.bar_chart(viz)

# Deep Dive page shows per-course breakdown and contribution
if page == "Deep Dive":
    st.header("Deep Dive")
    if courses_df.empty:
        st.info("No courses to inspect. Add courses on the Edit Courses page.")
    else:
        course_names = [f"{i+1}: {n if n else 'Unnamed'}" for i, n in enumerate(courses_df["name"].tolist())]
        # If a deep-dive index was set by clicking a card, pre-select that course
        default_pos = 0
        if "deep_dive_index" in st.session_state:
            target_idx = st.session_state.get("deep_dive_index")
            try:
                # course_names are numbered starting at 1
                prefix = f"{int(target_idx)+1}:"
                for p, nm in enumerate(course_names):
                    if nm.startswith(prefix):
                        default_pos = p
                        break
            except Exception:
                default_pos = 0
        choice = st.selectbox("Select a course to inspect", course_names, index=default_pos)
        idx = int(choice.split(":")[0]) - 1
        sel = courses_df.iloc[idx]
        st.markdown(f"**{sel['name']}** — Credits: {int(sel['credits'])} — Effective grade: {sel['effective_grade']:.2f}")
        st.write(f"Contribution to GPA (quality points): {sel['credits'] * sel['effective_grade']:.2f}")
        comps = parsed_breakdowns[idx] if idx < len(parsed_breakdowns) else []
        if comps:
            st.subheader("Components")
            st.table(pd.DataFrame(comps))
        else:
            st.write("No breakdown provided — using course-level expected GPA.")

        # Feedback from local LLM or heuristic
        st.subheader("Improvement feedback")
        if st.session_state.get("enable_local_llm", False):
            st.caption("Using local LLM model (configured in Settings)")
        else:
            st.caption("Using built-in heuristic feedback (no local LLM configured)")

        def heuristic_feedback(name, credits, effective_grade, components, target):
            tips = []
            # If overall below target, suggest high-impact components
            if effective_grade < target:
                tips.append(f"Current effective grade {effective_grade:.2f} is below target {target:.2f}.")
                # rank components by weight
                if components:
                    comps_sorted = sorted(components, key=lambda c: -abs(c.get("weight", 0)))
                    top = comps_sorted[0]
                    tips.append(f"Focus on '{top.get('name')}' (weight {top.get('weight')}) — improving it yields biggest GPA impact.")
                else:
                    tips.append("No component breakdown — focus on assignments/exams with largest credit or re-assess study time.")
            else:
                tips.append("You're on track for this course — maintain current performance and keep an eye on high-weight items.")
            # low-grade components
            for c in components or []:
                if c.get("grade", 0) < effective_grade and c.get("weight", 0) > 0:
                    tips.append(f"Component '{c.get('name')}' grade {c.get('grade'):.2f} is below course effective grade — investigate remediation.")
            return "\n".join(tips)

        # we'll call the generic run_local_llm helper defined earlier

        if st.button("Get improvement feedback"):
            comps_for_prompt = comps or []
            prompt_lines = [f"Course: {sel['name']}", f"Credits: {int(sel['credits'])}", f"Effective grade: {sel['effective_grade']:.2f}", f"Target GPA: {st.session_state.get('default_target_gpa', 3.0):.2f}"]
            if comps_for_prompt:
                prompt_lines.append("Components:")
                for c in comps_for_prompt:
                    prompt_lines.append(f"- {c.get('name')}: weight={c.get('weight')} grade={c.get('grade')}")
            prompt = "\n".join(prompt_lines) + "\n\nProvide concise suggestions to improve grades, prioritizing high-impact, actionable steps."

            if st.session_state.get("enable_local_llm", False) and st.session_state.get("local_llm_model_path"):
                model_path = st.session_state.get("local_llm_model_path")
                max_t = int(st.session_state.get("local_llm_max_tokens", 150))
                backend = st.session_state.get("local_llm_backend", "gpt4all")
                out, err = run_local_llm(prompt, backend, model_path, max_t)
                if out:
                    st.text_area("LLM feedback", value=out, height=200)
                else:
                    st.error(f"LLM feedback failed: {err}. Showing heuristic feedback instead.")
                    st.write(heuristic_feedback(sel['name'], sel['credits'], sel['effective_grade'], comps_for_prompt, st.session_state.get('default_target_gpa', 3.0)))
            else:
                st.write(heuristic_feedback(sel['name'], sel['credits'], sel['effective_grade'], comps_for_prompt, st.session_state.get('default_target_gpa', 3.0)))

# Settings page
if page == "Settings":
    st.header("Settings")
    st.write("Configure persistence, defaults, and display options.")

    # Defaults
    st.subheader("Defaults")
    st.number_input("Default target GPA", min_value=0.00, max_value=4.33, step=0.01, value=st.session_state.get("default_target_gpa", 3.00), key="default_target_gpa")
    st.number_input("Default number of course rows", min_value=1, max_value=20, step=1, value=st.session_state.get("default_rows", st.session_state.get("rows", 3)), key="default_rows")

    # Persistence
    st.subheader("Persistence")
    st.checkbox("Autosave to cookies on edit", value=st.session_state.get("autosave", False), key="autosave")
    st.number_input("Cookie TTL (days)", min_value=1, max_value=3650, step=1, value=st.session_state.get("cookie_ttl", 365), key="cookie_ttl")

    # Display / calculation toggles
    st.subheader("Display & Calculations")
    st.checkbox("Use component breakdowns for effective grade calculation", value=st.session_state.get("use_breakdowns", True), key="use_breakdowns")

    # Local LLM settings
    st.subheader("Local LLM (optional)")
    st.checkbox("Enable local LLM feedback", value=st.session_state.get("enable_local_llm", False), key="enable_local_llm")
    st.selectbox("Local LLM backend", options=["gpt4all", "llama_cpp"], index=0, key="local_llm_backend")
    st.text_input("Local LLM model name/path", value=st.session_state.get("local_llm_model_path", ""), key="local_llm_model_path")
    st.number_input("Local LLM max tokens", min_value=16, max_value=2048, step=1, value=st.session_state.get("local_llm_max_tokens", 150), key="local_llm_max_tokens")

    # If user recently downloaded a model, offer quick-open
    last_dir = st.session_state.get("last_downloaded_dir")
    if last_dir:
        st.info(f"Last downloaded model folder: {last_dir}")
        if st.button("Open last downloaded folder"):
            try:
                import subprocess
                subprocess.run(["open", last_dir])
            except Exception as e:
                st.error(f"Could not open folder: {e}")

    st.markdown("---")
    st.caption("If you don't have a local model file, select an example source below, then paste a direct file URL or use the Download button.")
    # Helpful example links and quick-set buttons (prefill the download URL)
    st.markdown("**Model sources / examples**")
    st.markdown("- gpt4all models: https://gpt4all.io/models/\n- llama.cpp releases: https://github.com/ggerganov/llama.cpp/releases\n- Hugging Face model hub: https://huggingface.co/models")
    col_a, col_b = st.columns(2)
    if col_a.button("Use example gpt4all page URL"):
        # set session_state before the widget (we'll rerun)
        st.session_state["local_llm_download_url"] = "https://gpt4all.io/models/"
        safe_rerun()
    if col_b.button("Use example llama.cpp releases URL"):
        st.session_state["local_llm_download_url"] = "https://github.com/ggerganov/llama.cpp/releases"
        safe_rerun()
    # URL input
    st.text_input("Model download URL", value=st.session_state.get("local_llm_download_url", ""), key="local_llm_download_url")
    if st.button("Download model into app"):
        url = st.session_state.get("local_llm_download_url", "").strip()
        backend = st.session_state.get("local_llm_backend", "gpt4all")
        if not url:
            st.error("Please provide a download URL for the model.")
        else:
            dest_dir = os.path.join(os.getcwd(), "models", backend)
            os.makedirs(dest_dir, exist_ok=True)
            filename = os.path.basename(urllib.parse.urlparse(url).path) or "model.bin"
            dest = os.path.join(dest_dir, filename)
            # Try streaming download with requests to show progress, fall back to urllib
            try:
                import requests
                with st.spinner("Downloading model — this may take a while depending on file size and connection..."):
                    resp = requests.get(url, stream=True, timeout=30)
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0))
                    chunk_size = 8192
                    downloaded = 0
                    prog = st.progress(0)
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total:
                                    prog.progress(min(100, int(downloaded * 100 / total)))
                    st.session_state["local_llm_model_path"] = dest
                    st.session_state["last_downloaded_dir"] = dest_dir
                    st.success(f"Model downloaded to {dest}")
                    st.markdown(f"Downloaded to: {dest}")
                    if st.button("Open downloaded folder", key=f"open_folder_{filename}"):
                        try:
                            import subprocess
                            subprocess.run(["open", dest_dir])
                        except Exception as _e:
                            st.error(f"Could not open folder: {_e}")
            except Exception as e:
                # fallback
                try:
                    with st.spinner("Downloading model (fallback)..."):
                        urllib.request.urlretrieve(url, dest)
                    st.session_state["local_llm_model_path"] = dest
                    st.session_state["last_downloaded_dir"] = dest_dir
                    st.success(f"Model downloaded to {dest}")
                    st.markdown(f"Downloaded to: {dest}")
                    if st.button("Open downloaded folder", key=f"open_folder_fb_{filename}"):
                        try:
                            import subprocess
                            subprocess.run(["open", dest_dir])
                        except Exception as _e:
                            st.error(f"Could not open folder: {_e}")
                except Exception as e2:
                    st.error(f"Model download failed: {e2}")

    # Export / Import
    st.subheader("Export / Import")
    export_json = json.dumps({"courses": course_data}, indent=2)
    st.download_button("Export courses JSON", export_json, file_name="courses.json", mime="application/json")

    uploaded = st.file_uploader("Import courses JSON", type=["json"])
    if uploaded is not None:
        try:
            payload = json.load(uploaded)
            cats = payload.get("courses") if isinstance(payload, dict) and payload.get("courses") is not None else payload
            if not isinstance(cats, list):
                st.error("Imported JSON must contain a top-level `courses` list or be a list of courses.")
            else:
                # populate session_state with imported data
                for i, c in enumerate(cats):
                    st.session_state[f"name_{i}"] = c.get("name", "")
                    st.session_state[f"credits_{i}"] = int(c.get("credits", 0))
                    st.session_state[f"grade_{i}"] = float(c.get("grade", 0.0))
                    # components if present
                    comps = c.get("components") or parse_breakdown_lines(c.get("breakdown_raw", ""))
                    st.session_state[f"comp_count_{i}"] = len(comps)
                    for j, comp in enumerate(comps):
                        st.session_state[f"comp_name_{i}_{j}"] = comp.get("name", "")
                        st.session_state[f"comp_weight_{i}_{j}"] = float(comp.get("weight", 0.0))
                        st.session_state[f"comp_grade_{i}_{j}"] = float(comp.get("grade", 0.0))
                st.session_state["rows"] = max(len(cats), 1)
                st.success("Imported courses into session state. Check Edit Courses to review.")
        except Exception as e:
            st.error(f"Failed to import JSON: {e}")

    # Save / Clear cookies
    st.subheader("Persistence Actions")
    if st.button("Save courses to cookies"):
        payload = {"courses": course_data}
        b64 = encode_data_for_cookie(payload)
        inject_set_cookie_and_reload(b64)

    if st.button("Clear saved cookie data"):
        inject_clear_cookie_and_reload()

    # Reset session
    if st.button("Reset all session data"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        safe_rerun()