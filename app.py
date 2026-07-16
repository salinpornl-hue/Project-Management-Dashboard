import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

# 1. Page Configuration
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
    # เพิ่ม per_page=100 เพื่อดึงข้อมูลให้ครอบคลุมขึ้น
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
    """คำนวณ % จาก Checklist [x] และ [ ] ใน Issue Body"""
    if not body:
        return 100.0 if status == "COMPLETED" else 0.0
    
    checked = body.lower().count("[x]")
    unchecked = body.lower().count("[ ]")
    total = checked + unchecked
    
    if total > 0:
        return (checked / total) * 100
    return 100.0 if status == "COMPLETED" else 0.0

# ใช้วันที่ปัจจุบันของระบบ
TODAY = datetime.now()

# --- UI: Top Toolbar ---
st.markdown("### 🏗️ BuildPM - Project Schedule")

t_col1, t_col2, t_col3 = st.columns([3, 1, 2])
with t_col1:
    search_query = st.text_input("🔍 Search tasks...", placeholder="พิมพ์ชื่อ Task...")
with t_col2:
    # เพิ่มตัวกรองสถานะที่ใช้งานได้จริง
    task_filter = st.selectbox("▽ FILTER STATUS", ["All Tasks", "IN PROGRESS", "DELAY", "COMPLETED"])
with t_col3:
    st.markdown("<br>", unsafe_allow_html=True) # จัดปุ่มให้ตรงบรรทัด
    if st.button("🔄 Refresh Data"):
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

        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        
        days = (end_date - start_date).days + 1
        
        # ตรวจสอบสถานะ
        state = task.get('state')
        if state == 'closed':
            status = "COMPLETED"
        elif TODAY > end_date:
            status = "DELAY"
        else:
            status = "IN PROGRESS"
            
        # การดึงผู้รับผิดชอบและ Labels
        assignees = ", ".join([a['login'] for a in task.get('assignees', [])]) if task.get('assignees') else "Unassigned"
        labels = ", ".join([l['name'] for l in task.get('labels', [])])
            
        # คำนวณ % การทำงาน
        plan_pct = min(100.0, max(0.0, ((TODAY - start_date).days / days) * 100)) if days > 0 else 0
        act_pct = calc_progress_from_checklist(body, status)

        df_data.append({
            "ID": task['number'],
            "WBS": str(i+1),
            "TASK NAME": task['title'],
            "ASSIGNEE": assignees,
            "START": start_date.date(), # <--- เปลี่ยนตรงนี้ (ใส่ .date() เพื่อตัดเวลาออก)
            "FINISH": end_date.date(),  # <--- เปลี่ยนตรงนี้ (ใส่ .date() เพื่อตัดเวลาออก)
            "DAYS": days,
            "% PLAN": f"{plan_pct:.0f}%",
            "% ACT.": f"{act_pct:.0f}%",
            "STATUS": status,
            "LABELS": labels,
            "_raw_start": start_date 
        })
        
    df = pd.DataFrame(df_data)
    
    # 1. ใช้งาน Search
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
        
    # 2. ใช้งาน Filter Status
    if task_filter != "All Tasks":
        df = df[df["STATUS"] == task_filter]
        
    df = df.sort_values("_raw_start").reset_index(drop=True)
    df_display = df.drop(columns=["_raw_start"])

    # คำนวณความสูงแบบไดนามิก (จำนวน Row * 35px + ขอบ) ต่ำสุดที่ 400px
    dynamic_height = max(400, len(df) * 35 + 100)

    # ==========================================
    # 🗂️ ส่วนแสดงผล: ซ้าย (Table) ขวา (Gantt)
    # ==========================================
    if not df.empty:
        col_left, col_right = st.columns([1.5, 1.5])
        
        with col_left:
            st.markdown("**📋 Task Details** *(Interactive Table - สามารถแก้ไขข้อมูลได้)*")
            # ใช้ st.data_editor แทน st.dataframe เพื่อให้เป็น Interactive Table
            edited_df = st.data_editor(
                df_display,
                hide_index=True,
                use_container_width=True,
                height=dynamic_height,
                column_config={
                    "STATUS": st.column_config.SelectboxColumn("STATUS", options=["IN PROGRESS", "DELAY", "COMPLETED"]),
                    "START": st.column_config.DateColumn("START", format="YYYY-MM-DD"),
                    "FINISH": st.column_config.DateColumn("FINISH", format="YYYY-MM-DD")
                }
            )
            
        with col_right:
            st.markdown("**📅 Gantt Chart Timeline**")
            # เพิ่ม text="% ACT." เพื่อแสดงความคืบหน้าบนกราฟ
            fig = px.timeline(
                df, 
                x_start="START", 
                x_end="FINISH", 
                y="TASK NAME", 
                color="STATUS",
                text="% ACT.", # แสดง % บนแท่งกราฟ
                color_discrete_map={
                    "COMPLETED": "#00C853", 
                    "IN PROGRESS": "#29B6F6", 
                    "DELAY": "#FF5252"        
                },
                hover_data=["ASSIGNEE", "DAYS", "% PLAN", "% ACT."]
            )
            fig.update_traces(textposition='inside', textfont_color='white')
            fig.update_yaxes(autorange="reversed", title=None)
            fig.update_xaxes(title=None, side="top")
            fig.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=dynamic_height, # ใช้ความสูงแบบไดนามิก
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("ไม่พบข้อมูลที่ตรงกับเงื่อนไขการค้นหา/ตัวกรอง")

else:
    st.info("ไม่มีงานในระบบ กดแถบด้านข้างเพื่อสร้างงานใหม่")


# --- Sidebar: จัดการงาน (Create / Update / Close) ---
with st.sidebar:
    st.header("🛠️ Task Management")
    tab1, tab2 = st.tabs(["➕ Create", "📝 Update/Close"])
    
    with tab1:
        with st.form("new_task_form", clear_on_submit=True):
            new_task_title = st.text_input("Task Name")
            start_d = st.date_input("Start Date", value=TODAY)
            end_d = st.date_input("Finish Date", value=TODAY + timedelta(days=5))
            new_task_desc = st.text_area("Description (เพิ่ม checklist เช่น - [ ] งานย่อย 1)")
            
            if st.form_submit_button("Submit Task", type="primary", use_container_width=True):
                if start_d > end_d:
                    st.error("วันที่เริ่มต้องมาก่อนวันสิ้นสุด!")
                elif not new_task_title:
                    st.warning("กรุณาใส่ชื่องาน")
                else:
                    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
                    body = f"📅 **Timeline:** {start_d.strftime('%Y-%m-%d')} to {end_d.strftime('%Y-%m-%d')}\n\n{new_task_desc}"
                    res = requests.post(url, headers=get_headers(), json={"title": new_task_title, "body": body})
                    if res.status_code == 201:
                        st.success("สร้างงานสำเร็จ!")
                        st.cache_data.clear()
                        st.rerun()

    with tab2:
        if 'df' in locals() and not df.empty:
            task_list = df['ID'].astype(str) + " : " + df['TASK NAME']
            selected_task = st.selectbox("เลือกงานที่ต้องการอัปเดต", task_list)
            
            if selected_task:
                task_id = selected_task.split(" : ")[0]
                new_state = st.radio("สถานะงานใน GitHub", ["open", "closed"], index=0)
                
                if st.button("บันทึกการเปลี่ยนแปลง", type="primary", use_container_width=True):
                    update_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{task_id}"
                    payload = {"state": new_state}
                    res = requests.patch(update_url, headers=get_headers(), json=payload)
                    
                    if res.status_code == 200:
                        st.success(f"อัปเดตงาน #{task_id} สำเร็จ!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("เกิดข้อผิดพลาดในการอัปเดต")
