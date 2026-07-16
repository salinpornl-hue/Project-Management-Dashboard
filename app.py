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
    match = re.search(r"📊 \*\*Actual Progress:\*\* (\d+(?:\.\d+)?)%", str(body))
    if match:
        return min(100.0, max(0.0, float(match.group(1))))
        
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
# 6. Reactive Data Processing Engine
# ==========================================
df_data = []
if issues_only:
    for task in issues_only:
        body = task.get('body', '')
        state = task.get('state')
        start_str, end_str = parse_dates_from_body(body, task.get('created_at'))
        
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        act_pct = calc_progress_from_checklist(body, state)
        
        assignees = task.get("assignees", [])
        assignee_names = ", ".join([a["login"] for a in assignees]) if assignees else ""
        
        df_data.append({
            "ID": task['number'],
            "TASK NAME": task['title'],
            "ASSIGNEE": assignee_names, 
            "START": start_date,
            "FINISH": end_date,
            "% ACT.": act_pct,
            "_raw_body": body,
            "_state": state
        })

if df_data:
    df = pd.DataFrame(df_data).sort_values("START").reset_index(drop=True)
else:
    df = pd.DataFrame(columns=["ID", "TASK NAME", "ASSIGNEE", "START", "FINISH", "% ACT.", "_raw_body", "_state"])

# ดักจับ Live Edits ที่พึ่งพิมพ์สดจากตารางตารางข้อมูล
pending_changes = st.session_state.get("task_editor", {})
edited_rows = pending_changes.get("edited_rows", {})

for row_str, changes in edited_rows.items():
    row_idx = int(row_str)
    if row_idx < len(df):
        for col_name, new_val in changes.items():
            if col_name in ["START", "FINISH"]:
                df.at[row_idx, col_name] = datetime.strptime(new_val, "%Y-%m-%d").date() if isinstance(new_val, str) else new_val
            elif col_name == "% ACT.":
                df.at[row_idx, col_name] = float(new_val) if new_val is not None else 0.0
            else:
                df.at[row_idx, col_name] = new_val

# ประมวลผลสถานะและประกอบร่างโมเดลสำหรับส่งให้แท่งกราฟ
gantt_data = []
if not df.empty:
    for idx, row in df.iterrows():
        start_date = row["START"]
        end_date = row["FINISH"]
        act_pct = row["% ACT."]
        state = row["_state"]
        
        total_days = calculate_days_by_mode(start_date, end_date, day_mode)
        elapsed_days = calculate_days_by_mode(start_date, cut_off_date, day_mode)
        
        plan_pct = max(0.0, min(100.0, (elapsed_days / total_days) * 100)) if total_days > 0 else 0.0
        fut_pct = 100.0 - plan_pct
        
        if state == 'closed' or act_pct >= 100.0:
            status = "COMPLETED"
        elif act_pct < plan_pct:
            status = "DELAY"
        else:
            status = "ON TRACK"
            
        unique_name = f"{row['ID']} - {row['TASK NAME']}"
        
        df.at[idx, "DAYS"] = total_days
        df.at[idx, "% PLAN"] = plan_pct
        df.at[idx, "STATUS"] = status
        df.at[idx, "% FUT"] = fut_pct
        df.at[idx, "UNIQUE_TASK"] = unique_name
        
        gantt_start = datetime.combine(start_date, time(0, 0, 0))
        gantt_finish = datetime.combine(end_date, time(23, 59, 59))
        
        # 💡 ใหม่: สร้างข้อความรูปแบบขีดคั่นแบ่งส่วนความคืบหน้า (เช่น | 45%) ฝังเข้าตัวแปรตัวถัง
        progress_marker = f"<b>| {int(act_pct)}%</b>"
        
        gantt_data.append({
            "UNIQUE_TASK": unique_name,
            "TASK NAME": row['TASK NAME'],
            "START": gantt_start,
            "FINISH": gantt_finish,
            "STATUS": status,
            "PROGRESS_MARKER": progress_marker  # ส่งขีดมาร์กเกอร์เข้าไปใช้ในกราฟ
        })
        
df_gantt = pd.DataFrame(gantt_data) if gantt_data else pd.DataFrame()

if search_query and not df.empty:
    df = df[df["TASK NAME"].str.contains(search_query, case=False)]
    if not df_gantt.empty:
        df_gantt = df_gantt[df_gantt["TASK NAME"].str.contains(search_query, case=False)]
        
if task_filter != "All" and not df.empty:
    df = df[df["STATUS"] == task_filter]
    if not df_gantt.empty:
        df_gantt = df_gantt[df_gantt["STATUS"] == task_filter]

# ==========================================
# 7. UI: Bulk Edit Save System
# ==========================================
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
                for row_str in deleted_rows:
                    row_idx = int(row_str)
                    issue_id = df.loc[row_idx, "ID"]
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
                for row_str, changes in edited_rows.items():
                    row_idx = int(row_str)
                    if row_idx in deleted_rows: continue
                    issue_id = df.loc[row_idx, "ID"]
                    current_body = str(df.loc[row_idx, "_raw_body"])
                    payload = {}
                    
                    if "TASK NAME" in changes: payload["title"] = df.loc[row_idx, "TASK NAME"]
                    if "ASSIGNEE" in changes:
                        payload["assignees"] = [a.strip() for a in df.loc[row_idx, "ASSIGNEE"].split(",") if a.strip()]
                    
                    if "START" in changes or "FINISH" in changes:
                        new_start = str(df.loc[row_idx, "START"])
                        new_finish = str(df.loc[row_idx, "FINISH"])
                        if re.search(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", current_body):
                            current_body = re.sub(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", f"📅 **Timeline:** {new_start} to {new_finish}", current_body)
                        else:
                            current_body = f"📅 **Timeline:** {new_start} to {new_finish}\n\n{current_body}"
                    
                    if "% ACT." in changes:
                        new_act = df.loc[row_idx, "% ACT."]
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
df_display = pd.DataFrame(columns=["ID", "ASSIGNEE", "TASK NAME", "START", "FINISH", "DAYS", "% PLAN", "% ACT.", "STATUS", "% FUT"])
if not df.empty:
    df_display = df[["ID", "ASSIGNEE", "TASK NAME", "START", "FINISH", "DAYS", "% PLAN", "% ACT.", "STATUS", "% FUT"]]

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
            "% ACT.": st.column_config.NumberColumn("% ACT.", format="%d%%", min_value=0, max_value=100, width="small"),
            "STATUS": st.column_config.TextColumn("STATUS", width="small"),
            "% FUT": st.column_config.ProgressColumn("% FUT", format="%.0f%%", min_value=0, max_value=100, width="small"),
        }
    )

with right_col:
    st.markdown("##### 📅 Gantt Chart &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span style='font-size:12px; border-left:10px solid #81C784; padding-left:4px;'>COMPLETED</span> &nbsp;&nbsp; <span style='font-size:12px; border-left:10px solid #90CAF9; padding-left:4px;'>ON TRACK</span> &nbsp;&nbsp; <span style='font-size:12px; border-left:10px solid #EF9A9A; padding-left:4px;'>DELAY</span>", unsafe_allow_html=True)
    if not df_gantt.empty:
        # 💡 ใหม่: เพิ่ม parameter `text="PROGRESS_MARKER"` เข้าไปในพารามิเตอร์เริ่มต้นของโครงสร้างรูปวาด
        fig = px.timeline(
            df_gantt, 
            x_start="START", 
            x_end="FINISH", 
            y="UNIQUE_TASK", 
            color="STATUS",
            text="PROGRESS_MARKER",
            color_discrete_map={
                "COMPLETED": "#81C784",
                "ON TRACK": "#90CAF9",
                "DELAY": "#EF9A9A"
            }
        )
        
        # 💡 ใหม่: ตั้งค่าตำแหน่งให้อักษรขีดแสดงกึ่งกลางแท่ง (inside) และปรับสีให้อ่านคมชัดขึ้น
        fig.update_traces(
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="#1A1A1A", size=11, family="Courier New, monospace"),
            marker_line_color='rgba(100, 120, 150, 0.4)', 
            marker_line_width=1, 
            opacity=0.95
        )
        
        ordered_tasks = df["UNIQUE_TASK"].tolist() if not df.empty else []
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
