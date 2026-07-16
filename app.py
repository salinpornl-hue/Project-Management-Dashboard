import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta, time

# ==========================================
# 1. Page Configuration & Custom Premium CSS
# ==========================================
st.set_page_config(page_title="BuildPM | Project Management Dashboard", layout="wide", page_icon="🏗️")

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    div[data-testid="stNotification"] { padding: 0.6rem; margin-bottom: 0.75rem; border-radius: 6px; }
    .stDataEditor { border: 1px solid #e0e0e0; border-radius: 6px; }
    .reportview-container .main .block-container{ max-width: 98%; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GitHub Secrets & Setup
# ==========================================
try:
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception as e:
    st.error("⚠️ Missing credentials in Streamlit Secrets. Please check your .streamlit/secrets.toml file.")
    st.stop()

def get_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

TODAY_DATE = datetime.now().date()

# ==========================================
# 3. Helper Functions
# ==========================================
@st.cache_data(ttl=60)
def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state=open&per_page=100"
    response = requests.get(url, headers=get_headers())
    return response.json() if response.status_code == 200 else []

def parse_dates_from_body(body, created_at):
    match = re.search(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", str(body))
    if match:
        return match.group(1), match.group(2)
    start = created_at[:10]
    end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=5)).strftime("%Y-%m-%d")
    return start, end

def calc_progress_from_checklist(body, state):
    # ตรวจสอบก่อนว่ามีแท็กความคืบหน้าที่ถูกพิมพ์ตรงจากตารางเซฟไว้หรือไม่
    match = re.search(r"📊 \*\*Actual Progress:\*\* (\d+(?:\.\d+)?)%", str(body))
    if match:
        return min(100.0, max(0.0, float(match.group(1))))
        
    # หากไม่มีแท็กพิมพ์ตรง ให้ถอยกลับไปคำนวณจากระบบ Checklist บน GitHub ตามเดิม
    if not body:
        return 100.0 if state == "closed" else 0.0
    checked = body.lower().count("[x]")
    unchecked = body.lower().count("[ ]")
    total = checked + unchecked
    if total > 0:
        return (checked / total) * 100
    return 100.0 if state == "closed" else 0.0

def calculate_days_by_mode(start, end, mode):
    if start > end:
        return 0
    if mode == "5-Day (Work Week)":
        working_days = 0
        current = start
        while current <= end:
            if current.weekday() < 5:
                working_days += 1
            current += timedelta(days=1)
        return working_days
    else:
        return (end - start).days + 1

# ==========================================
# 4. Fetch Base Data
# ==========================================
tasks = get_tasks()
issues_only = [t for t in tasks if 'pull_request' not in t]

# ==========================================
# 5. UI: Top Toolbar
# ==========================================
st.markdown("### 🏗️ BuildPM - Advanced Project Tracking")

raw_dates = [parse_dates_from_body(t.get('body', ''), t.get('created_at')) for t in issues_only] if issues_only else []
default_start = min([datetime.strptime(d[0], "%Y-%m-%d").date() for d in raw_dates]) - timedelta(days=2) if raw_dates else TODAY_DATE - timedelta(days=5)
default_end = max([datetime.strptime(d[1], "%Y-%m-%d").date() for d in raw_dates]) + timedelta(days=5) if raw_dates else TODAY_DATE + timedelta(days=25)

t_col1, t_col2, t_col3, t_col4, t_col5, t_col6, t_col7, t_col8 = st.columns([1.5, 1.2, 1.1, 1.1, 1.0, 1.0, 1.3, 0.9])

with t_col1:
    search_query = st.text_input("🔍 Search tasks...")
with t_col2:
    task_filter = st.selectbox("▽ STATUS FILTER", ["All", "ON TRACK", "DELAY", "COMPLETED"])
with t_col3:
    cut_off_date = st.date_input("✂️ CUT-OFF DATE", value=TODAY_DATE)
with t_col4:
    target_date = st.date_input("🎯 TARGET DATE", value=default_end - timedelta(days=3))
with t_col5:
    view_start = st.date_input("🗓️ ZOOM FROM", value=default_start)
with t_col6:
    view_end = st.date_input("🗓️ ZOOM TO", value=default_end)
with t_col7:
    day_mode = st.selectbox("📅 DAY CALCULATION", ["7-Day (Calendar)", "5-Day (Work Week)"])
with t_col8:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Sync GitHub", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ==========================================
# 6. Data Processing
# ==========================================
df_data = []
gantt_data = []

if issues_only:
    for i, task in enumerate(issues_only):
        body = task.get('body', '')
        state = task.get('state')
        start_str, end_str = parse_dates_from_body(body, task.get('created_at'))
        
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        
        total_days = calculate_days_by_mode(start_date, end_date, day_mode)
        elapsed_days = calculate_days_by_mode(start_date, cut_off_date, day_mode)
        
        if total_days > 0:
            plan_pct = max(0.0, min(100.0, (elapsed_days / total_days) * 100))
        else:
            plan_pct = 0.0
            
        act_pct = calc_progress_from_checklist(body, state)
        fut_pct = 100.0 - plan_pct
        
        if state == 'closed':
            status = "COMPLETED"
        elif act_pct < plan_pct:
            status = "DELAY"
        else:
            status = "ON TRACK"

        assignees = task.get("assignees", [])
        assignee_names = ", ".join([a["login"] for a in assignees]) if assignees else ""
        unique_name = f"{task['number']} - {task['title']}"

        df_data.append({
            "ID": task['number'],
            "UNIQUE_TASK": unique_name,
            "ASSIGNEE": assignee_names, 
            "TASK NAME": task['title'],
            "START": start_date,
            "FINISH": end_date,
            "DAYS": total_days,
            "% PLAN": plan_pct,
            "% ACT.": act_pct, 
            "STATUS": status,
            "% FUT": fut_pct,
            "_raw_start": start_date,
            "_raw_body": body 
        })
        
        gantt_start = datetime.combine(start_date, time(0, 0, 0))
        gantt_finish = datetime.combine(end_date, time(23, 59, 59))
        gantt_data.append({
            "UNIQUE_TASK": unique_name, 
            "TASK NAME": task['title'], 
            "START": gantt_start, 
            "FINISH": gantt_finish, 
            "STATUS": status, 
            "_raw_start": start_date
        })

df = pd.DataFrame(df_data).sort_values("_raw_start").reset_index(drop=True) if not pd.DataFrame(df_data).empty else pd.DataFrame(columns=["ID", "UNIQUE_TASK", "ASSIGNEE", "TASK NAME", "START", "FINISH", "DAYS", "% PLAN", "% ACT.", "STATUS", "% FUT", "_raw_start", "_raw_body"])
df_gantt = pd.DataFrame(gantt_data).sort_values("_raw_start").reset_index(drop=True) if gantt_data else pd.DataFrame()

if search_query and not df.empty:
    df = df[df["TASK NAME"].str.contains(search_query, case=False)]
    df_gantt = df_gantt[df_gantt["TASK NAME"].str.contains(search_query, case=False)]
if task_filter != "All" and not df.empty:
    df = df[df["STATUS"] == task_filter]
    valid_tasks = df["UNIQUE_TASK"].tolist()
    df_gantt = df_gantt[df_gantt["UNIQUE_TASK"].isin(valid_tasks)]

# ==========================================
# 7. UI: Bulk Edit Save System
# ==========================================
pending_changes = st.session_state.get("task_editor", {})
edited_rows = pending_changes.get("edited_rows", {})
added_rows = pending_changes.get("added_rows", [])
deleted_rows = pending_changes.get("deleted_rows", [])
total_changes = len(edited_rows) + len(added_rows) + len(deleted_rows)

if total_changes > 0:
    c_box1, c_box2 = st.columns([0.75, 0.25])
    with c_box1:
        st.warning(f"⚠️ **Unsaved Changes Pending:** คุณมีการเปลี่ยนแปลงข้อมูลค้างอยู่ {total_changes} รายการที่ยังไม่ได้บันทึกลง GitHub")
    with c_box2:
        if st.button("💾 Save Changes to GitHub", type="primary", use_container_width=True):
            has_error = False
            with st.spinner("Saving configurations..."):
                for row_idx in deleted_rows:
                    issue_id = df["ID"].iloc[row_idx]
                    requests.patch(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}", headers=get_headers(), json={"state": "closed"})
                for new_row in added_rows:
                    title = new_row.get("TASK NAME", "Untitled Task")
                    start = str(new_row.get("START", TODAY_DATE.strftime("%Y-%m-%d")))
                    finish = str(new_row.get("FINISH", TODAY_DATE.strftime("%Y-%m-%d")))
                    assignee_str = str(new_row.get("ASSIGNEE", ""))
                    body = f"📅 **Timeline:** {start} to {finish}\n\n📊 **Actual Progress:** 0%\n\n- [ ] Checklist 1"
                    payload = {"title": title, "body": body}
                    if assignee_str.strip():
                        payload["assignees"] = [a.strip() for a in assignee_str.split(",") if a.strip()]
                    requests.post(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues", headers=get_headers(), json=payload)
                
                for row_idx, changes in edited_rows.items():
                    if row_idx in deleted_rows: continue
                    issue_id = df["ID"].iloc[row_idx]
                    current_body = str(df["_raw_body"].iloc[row_idx])
                    payload = {}
                    if "TASK NAME" in changes: payload["title"] = changes["TASK NAME"]
                    if "ASSIGNEE" in changes:
                        payload["assignees"] = [a.strip() for a in changes["ASSIGNEE"].split(",") if a.strip()]
                    
                    if "START" in changes or "FINISH" in changes:
                        new_start = str(changes.get("START", df["START"].iloc[row_idx]))
                        new_finish = str(changes.get("FINISH", df["FINISH"].iloc[row_idx]))
                        if re.search(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", current_body):
                            current_body = re.sub(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", f"📅 **Timeline:** {new_start} to {new_finish}", current_body)
                        else:
                            current_body = f"📅 **Timeline:** {new_start} to {new_finish}\n\n{current_body}"
                    
                    # ตรวจจับกรณีผู้ใช้แก้ไขตัวเลขจากตาราง แล้วเขียนบันทึกฝังลงไปในเนื้อหา GitHub
                    if "% ACT." in changes:
                        new_act = changes["% ACT."]
                        if re.search(r"📊 \*\*Actual Progress:\*\* \d+(?:\.\d+)?%", current_body):
                            current_body = re.sub(r"📊 \*\*Actual Progress:\*\* \d+(?:\.\d+)?%", f"📊 **Actual Progress:** {new_act}%", current_body)
                        else:
                            current_body = f"{current_body}\n\n📊 **Actual Progress:** {new_act}%"
                    
                    if "START" in changes or "FINISH" in changes or "% ACT." in changes or "TASK NAME" in changes or "ASSIGNEE" in changes:
                        payload["body"] = current_body

                    if payload:
                        requests.patch(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}", headers=get_headers(), json=payload)
            if not has_error:
                st.success("✅ Synchronized data successfully!")
                st.cache_data.clear()
                st.rerun()

# ==========================================
# 8. Render Split-View UI
# ==========================================
df_display = df.drop(columns=["UNIQUE_TASK", "_raw_start", "_raw_body"]) if not df.empty else pd.DataFrame(columns=["ID", "ASSIGNEE", "TASK NAME", "START", "FINISH", "DAYS", "% PLAN", "% ACT.", "STATUS", "% FUT"])

ROW_HEIGHT = 35.6
HEADER_HEIGHT = 40.0
FOOTER_HEIGHT = 41.0 
EXACT_HEIGHT = int((len(df_display) * ROW_HEIGHT) + HEADER_HEIGHT + FOOTER_HEIGHT) if len(df_display) > 0 else 160

left_col, right_col = st.columns([0.54, 0.46])

with left_col:
    st.markdown("##### 📊 Task Spreadsheet Dataset")
    edited_df = st.data_editor(
        df_display,
        key="task_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        height=EXACT_HEIGHT,
        disabled=["ID", "DAYS", "% PLAN", "STATUS", "% FUT"],
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "ASSIGNEE": st.column_config.TextColumn("ASSIGNEE", width="small"),
            "TASK NAME": st.column_config.TextColumn("TASK NAME", width="medium"),
            "START": st.column_config.DateColumn("START", format="DD/MM/YYYY", width="small"), 
            "FINISH": st.column_config.DateColumn("FINISH", format="DD/MM/YYYY", width="small"), 
            "DAYS": st.column_config.NumberColumn("DAYS", width="small"),
            "% PLAN": st.column_config.ProgressColumn("% PLAN", format="%.0f%%", min_value=0, max_value=100, width="small"),
            # 💡 แก้ไขจุดนี้: เปลี่ยนจาก ProgressColumn เป็น NumberColumn เพื่อเปิดให้คีย์ตัวเลขหรือกดเลื่อนเปอร์เซ็นต์ได้จริงแล้วครับ!
            "% ACT.": st.column_config.NumberColumn("% ACT.", format="%d%%", min_value=0, max_value=100, width="small"),
            "STATUS": st.column_config.TextColumn("STATUS", width="small"),
            "% FUT": st.column_config.ProgressColumn("% FUT", format="%.0f%%", min_value=0, max_value=100, width="small"),
        }
    )

with right_col:
    st.markdown("##### 📅 Gantt Chart &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span style='font-size:12px; border-left:10px solid #81C784; padding-left:4px;'>COMPLETED</span> &nbsp;&nbsp; <span style='font-size:12px; border-left:10px solid #90CAF9; padding-left:4px;'>ON TRACK</span> &nbsp;&nbsp; <span style='font-size:12px; border-left:10px solid #EF9A9A; padding-left:4px;'>DELAY</span>", unsafe_allow_html=True)
    if not df_gantt.empty:
        fig = px.timeline(
            df_gantt, 
            x_start="START", 
            x_end="FINISH", 
            y="UNIQUE_TASK", 
            color="STATUS",
            color_discrete_map={
                "COMPLETED": "#81C784",
                "ON TRACK": "#90CAF9",
                "DELAY": "#EF9A9A"
            }
        )
        
        fig.update_traces(marker_line_color='rgba(100, 120, 150, 0.4)', marker_line_width=1, opacity=0.95)
        
        ordered_tasks = df["UNIQUE_TASK"].tolist()
        fig.update_yaxes(autorange="reversed", categoryorder='array', categoryarray=ordered_tasks, visible=False, showgrid=False)
        
        xaxes_config = dict(
            side="top", title=None, tickformat="%d %b\n%a", 
            showgrid=True, gridcolor='rgba(220, 220, 220, 0.5)',
            dtick="86400000",
            range=[view_start.strftime("%Y-%m-%d"), view_end.strftime("%Y-%m-%d")]
        )
        if day_mode == "5-Day (Work Week)":
            xaxes_config["rangebreaks"] = [dict(bounds=["sat", "mon"])]
            
        fig.update_xaxes(**xaxes_config)
        
        fig.add_vline(x=cut_off_date.strftime("%Y-%m-%d 23:59:59"), line_width=1.5, line_dash="dash", line_color="#5D3FD3", annotation_text="CUT-OFF", annotation_position="top left", annotation=dict(font_size=9, font_color="white", bgcolor="#5D3FD3", borderpad=2))
        fig.add_vline(x=target_date.strftime("%Y-%m-%d 23:59:59"), line_width=1.5, line_dash="solid", line_color="#E3242B", annotation_text="TARGET", annotation_position="top right", annotation=dict(font_size=9, font_color="white", bgcolor="#E3242B", borderpad=2))
        
        fig.update_layout(
            margin=dict(l=0, r=5, t=HEADER_HEIGHT - 3.0, b=FOOTER_HEIGHT),
            height=EXACT_HEIGHT,
            showlegend=False,
            plot_bgcolor="white"
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.markdown(f"<div style='text-align: center; color: gray; line-height: {EXACT_HEIGHT}px; border: 1px dashed #ccc; border-radius: 6px;'>No timeline metrics matching criteria.</div>", unsafe_allow_html=True)
