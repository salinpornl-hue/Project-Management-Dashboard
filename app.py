import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

# 1. Page Configuration (ตั้งค่าเป็น Wide เพื่อใช้พื้นที่เต็มจอ)
st.set_page_config(page_title="BuildPM | Professional View", layout="wide", page_icon="🏗️")

# 2. Load Secrets
try:
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception as e:
    st.error("Missing credentials in Streamlit Secrets. Please check your .streamlit/secrets.toml file.")
    st.stop()

def get_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# --- Data Fetching & Parsing ---
@st.cache_data(ttl=60)
def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state=all&per_page=100"
    response = requests.get(url, headers=get_headers())
    return response.json() if response.status_code == 200 else []

def parse_dates_from_body(body, created_at):
    match = re.search(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", str(body))
    if match:
        return match.group(1), match.group(2)
    start = created_at[:10]
    end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=5)).strftime("%Y-%m-%d")
    return start, end

def calc_progress_from_checklist(body, status):
    if not body:
        return 100.0 if status == "COMPLETED" else 0.0
    checked = body.lower().count("[x]")
    unchecked = body.lower().count("[ ]")
    total = checked + unchecked
    if total > 0:
        return (checked / total) * 100
    return 100.0 if status == "COMPLETED" else 0.0

TODAY_DATE = datetime.now().date()

# --- UI: Top Toolbar (คล้ายในรูป) ---
st.markdown("### 🏗️ BuildPM - Project Management Suite")

t_col1, t_col2, t_col3, t_col4 = st.columns([3, 2, 2, 1])
with t_col1:
    search_query = st.text_input("🔍 Search tasks...", placeholder="พิมพ์ชื่อ Task...")
with t_col2:
    display_view = st.selectbox("☷ DISPLAY VIEW", ["Split-View (PM Style)", "Kanban Board"])
with t_col3:
    task_filter = st.selectbox("▽ FILTER STATUS", ["All Tasks", "IN PROGRESS", "DELAY", "COMPLETED"])
with t_col4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Sync GitHub", type="primary"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# --- Data Processing ---
tasks = get_tasks()
issues_only = [t for t in tasks if 'pull_request' not in t]

if issues_only:
    df_data = []
    for i, task in enumerate(issues_only):
        body = task.get('body', '')
        start_str, end_str = parse_dates_from_body(body, task.get('created_at'))
        
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        days = (end_date - start_date).days + 1
        
        state = task.get('state')
        if state == 'closed':
            status = "COMPLETED"
        elif TODAY_DATE > end_date:
            status = "DELAY"
        else:
            status = "IN PROGRESS"
            
        plan_pct = min(100.0, max(0.0, ((TODAY_DATE - start_date).days / days) * 100)) if days > 0 else 0
        act_pct = calc_progress_from_checklist(body, status)

        df_data.append({
            "ID": task['number'],
            "WBS": str(i+1),
            "TASK NAME": task['title'],
            "START": start_date,
            "FINISH": end_date,
            "DAYS": days,
            "% PLAN": plan_pct,
            "% ACT.": act_pct, 
            "STATUS": status,
            "_raw_start": start_date,
            "_raw_body": body 
        })
    
    df = pd.DataFrame(df_data)
    
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
    if task_filter != "All Tasks":
        df = df[df["STATUS"] == task_filter]
        
    # เรียงลำดับตามวันที่เริ่ม และ Reset Index ให้แถวตรงกับกราฟ
    df = df.sort_values("_raw_start").reset_index(drop=True)
    df_display = df.drop(columns=["_raw_start", "_raw_body"])

    if not df.empty:
        if display_view == "Split-View (PM Style)":
            
            # คำนวณความสูงแบบไดนามิก เพื่อให้ตารางกับกราฟสูงเท่ากัน (ป้องกันการเกิด Scroll bar ซ้อน)
            # ความสูง 1 แถวของ Streamlit ประมาณ 35px + ขอบและหัวตาราง
            ROW_HEIGHT = 35
            DYNAMIC_HEIGHT = max(300, (len(df) * ROW_HEIGHT) + 42)

            # --- แบ่งครึ่งหน้าจอ (ซ้าย 45% ตาราง : ขวา 55% กราฟ Gantt) ---
            left_col, right_col = st.columns([0.45, 0.55])
            
            with left_col:
                # ตาราง Data Editor (ฝั่งซ้าย)
                edited_df = st.data_editor(
                    df_display,
                    key="task_editor",
                    hide_index=True,
                    use_container_width=True,
                    height=DYNAMIC_HEIGHT,
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                        "WBS": st.column_config.TextColumn("WBS", disabled=True, width="small"),
                        "TASK NAME": st.column_config.TextColumn("TASK NAME", width="medium"),
                        "START": st.column_config.DateColumn("START", format="DD MMM YYYY"),
                        "FINISH": st.column_config.DateColumn("FINISH", format="DD MMM YYYY"),
                        "DAYS": st.column_config.NumberColumn("DAYS", disabled=True),
                        "% PLAN": st.column_config.ProgressColumn("% PLAN", format="%.0f%%", min_value=0, max_value=100),
                        "% ACT.": st.column_config.ProgressColumn("% ACT.", format="%.0f%%", min_value=0, max_value=100),
                        "STATUS": st.column_config.SelectboxColumn("STATUS", options=["IN PROGRESS", "DELAY", "COMPLETED"]),
                    }
                )

            with right_col:
                # กราฟ Gantt Chart (ฝั่งขวา)
                # ใช้ Plotly สร้างแท่ง Gantt แบบขอบมน (รูปทรงแท่ง)
                fig = px.timeline(
                    df, 
                    x_start="START", 
                    x_end="FINISH", 
                    y="TASK NAME", 
                    color="STATUS",
                    color_discrete_map={
                        "COMPLETED": "#b5e5c5", # สีเขียวอ่อนคล้ายในรูป
                        "IN PROGRESS": "#cde0f5", # สีฟ้าอ่อน
                        "DELAY": "#f5cdcd"  # สีแดงอ่อน
                    }
                )
                
                # กลับด้านแกน Y ให้แถวบนสุดตรงกับตาราง และ ซ่อนชื่อ Task ในแกน Y ทิ้ง (เพราะมีในตารางฝั่งซ้ายแล้ว)
                fig.update_yaxes(autorange="reversed", visible=False, showgrid=False)
                
                # ย้ายปฏิทินแกน X ไปไว้ด้านบน และจัดรูปแบบให้อ่านง่าย
                fig.update_xaxes(
                    side="top", 
                    title=None,
                    tickformat="%d %b\n%a", # เช่น 21 Jun / Mon
                    showgrid=True, gridcolor='rgba(200, 200, 200, 0.3)',
                    dtick="86400000" # ขีดบอกทุกๆ 1 วัน
                )
                
                # ปรับแต่ง Layout ให้พอดีกับความสูงของตารางฝั่งซ้ายเป๊ะๆ
                fig.update_layout(
                    margin=dict(l=0, r=0, t=40, b=0), # ลดขอบให้ชิด
                    height=DYNAMIC_HEIGHT,
                    showlegend=False, # ซ่อน Legend เพื่อประหยัดพื้นที่
                    plot_bgcolor="white"
                )
                
                # ลบปุ่ม Toolbars ของ Plotly ออกให้ดูคลีนเหมือนหน้าจอโปรแกรม
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            # --- 2-Way Sync Logic (ทำงานเมื่อแก้ข้อมูลในตารางฝั่งซ้าย) ---
            if st.session_state.task_editor["edited_rows"]:
                st.toast('กำลังซิงค์ข้อมูลกับ GitHub...', icon='🔄')
                edits = st.session_state.task_editor["edited_rows"]
                for row_idx, changes in edits.items():
                    issue_id = df["ID"].iloc[row_idx]
                    current_body = df["_raw_body"].iloc[row_idx]
                    payload = {}
                    
                    if "STATUS" in changes:
                        payload["state"] = "closed" if changes["STATUS"] == "COMPLETED" else "open"
                        
                    if "START" in changes or "FINISH" in changes:
                        new_start = str(changes.get("START", df["START"].iloc[row_idx]))
                        new_finish = str(changes.get("FINISH", df["FINISH"].iloc[row_idx]))
                        if re.search(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", current_body):
                            payload["body"] = re.sub(
                                r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}",
                                f"📅 **Timeline:** {new_start} to {new_finish}", current_body)
                        else:
                            payload["body"] = f"📅 **Timeline:** {new_start} to {new_finish}\n\n{current_body}"

                    if payload:
                        requests.patch(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}", headers=get_headers(), json=payload)
                st.cache_data.clear()
                st.rerun()

        # (ซ่อน Kanban Board ไว้เผื่อสลับดู)
        elif display_view == "Kanban Board":
            st.markdown("### 🗂️ Project Kanban Board")
            # โค้ด Kanban เดิม... (ละไว้เพื่อความกระชับ)

    else:
        st.warning("ไม่พบข้อมูลที่ตรงกับเงื่อนไขการค้นหา/ตัวกรอง")
else:
    st.info("ไม่มีงานในระบบ กดแถบด้านข้างเพื่อสร้างงานใหม่")
