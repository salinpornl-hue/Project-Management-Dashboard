import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

# 1. Page Configuration
st.set_page_config(page_title="BuildPM Task Tracker", layout="wide", page_icon="🏗️")

# 2. Load Secrets securely
try:
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception as e:
    st.error("Configuration Error: Missing credentials. Please configure GITHUB_TOKEN, REPO_OWNER, and REPO_NAME in Streamlit Secrets.")
    st.stop()

def get_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

# --- Functions สำหรับติดต่อ API ---

def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state=all" # ดึงมาทั้งงานที่เปิดและปิดแล้วเพื่อดูประวัติ
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch data: {response.status_code}")
        return []

def create_task(title, body, start_date, end_date):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    # ฝังวันที่ลงไปใน Description เพื่อเอามาใช้วาดกราฟ
    formatted_body = f"📅 **Timeline:** {start_date} to {end_date}\n\n---\n\n{body}"
    payload = {"title": title, "body": formatted_body}
    return requests.post(url, headers=get_headers(), json=payload)

def update_task_state(issue_number, state="closed"):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
    payload = {"state": state}
    return requests.patch(url, headers=get_headers(), json=payload)

# --- ฟังก์ชันสกัดข้อมูลเพื่อทำ Gantt Chart ---
def parse_dates_from_body(body, created_at):
    # ค้นหารูปแบบ "YYYY-MM-DD to YYYY-MM-DD"
    match = re.search(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", str(body))
    if match:
        return match.group(1), match.group(2)
    else:
        # ถ้าไม่มี ให้ใช้วันที่สร้างงานเป็นจุดเริ่มต้น และบวกไป 7 วันเป็นจุดสิ้นสุดจำลอง
        start = created_at[:10]
        end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        return start, end

# --- UI และการแสดงผล ---

st.title("🏗️ BuildPM - Project Management System")
st.write("Project tracking, timeline simulation, and task handover dashboard")
st.markdown("---")

tasks = get_tasks()
issues_only = [t for t in tasks if 'pull_request' not in t]

# ==========================================
# 📊 ส่วนที่ 1: ระบบแผนงาน (Gantt Chart)
# ==========================================
if issues_only:
    st.subheader("📅 Project Timeline (Gantt Chart)")
    
    # เตรียมข้อมูลใส่ DataFrame ของ Pandas
    df_data = []
    for task in issues_only:
        start_date, end_date = parse_dates_from_body(task.get('body'), task.get('created_at'))
        assignee = task.get('assignee', {}).get('login', 'Unassigned') if task.get('assignee') else 'Unassigned'
        status = "Completed" if task.get('state') == 'closed' else "In Progress"
        
        df_data.append({
            "Task": f"#{task['number']} {task['title']}",
            "Start": start_date,
            "Finish": end_date,
            "Assignee": assignee,
            "Status": status
        })
    
    if df_data:
        df = pd.DataFrame(df_data)
        # วาดกราฟแกนต์ด้วย Plotly
        fig = px.timeline(
            df, x_start="Start", x_end="Finish", y="Task", 
            color="Status", # แบ่งสีตามสถานะงาน
            color_discrete_map={"Completed": "#28a745", "In Progress": "#ffc107"},
            hover_data=["Assignee"]
        )
        fig.update_yaxes(autorange="reversed") # ให้งานที่สร้างก่อนอยู่บนสุด
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("ยังไม่มีข้อมูลสำหรับสร้างตารางเวลา กรุณาสร้างงานใหม่")

st.markdown("---")

# ==========================================
# 🗂️ ส่วนที่ 2: จัดการงาน (Task Cards)
# ==========================================
st.subheader("📋 Active Tasks")
active_tasks = [t for t in issues_only if t['state'] == 'open']

if not active_tasks:
    st.success("ไม่มีงานที่ค้างอยู่ เยี่ยมมาก!")
else:
    cols = st.columns(3)
    for index, task in enumerate(active_tasks):
        title = task.get('title', 'Untitled Task')
        body = task.get('body', '')
        assignee = task.get('assignee', {}).get('login', 'Unassigned') if task.get('assignee') else 'Unassigned'
        issue_number = task.get('number')
        
        col = cols[index % 3]
        with col:
            with st.container(border=True):
                st.markdown(f"#### 📌 {title}")
                st.caption(f"👤 Assignee: **{assignee}**")
                    
                with st.expander("ดูรายละเอียดงาน"):
                    st.markdown(body) # แสดงรายละเอียดรวมถึง Timeline ที่ฝังไว้
                
                # ปุ่มปิดงาน
                if st.button("ปิดงาน ✅", key=f"close_{issue_number}", type="primary", use_container_width=True):
                    res = update_task_state(issue_number, "closed")
                    if res.status_code == 200:
                        st.rerun()

# ==========================================
# ➕ ส่วนที่ 3: Sidebar สำหรับสร้างงานใหม่
# ==========================================
with st.sidebar:
    st.header("➕ Create New Task")
    new_task_title = st.text_input("Task Title (ชื่องาน)")
    
    # เพิ่ม Date Picker 
    col1, col2 = st.columns(2)
    with col1:
        start_d = st.date_input("Start Date")
    with col2:
        end_d = st.date_input("End Date")
        
    new_task_desc = st.text_area("Task Description (รายละเอียด)")
    
    if st.button("Create Task", type="primary", use_container_width=True):
        if not new_task_title.strip():
            st.warning("Please enter a Task Title.")
        elif start_d > end_d:
            st.error("วันที่เริ่มงาน ต้องมาก่อนวันสิ้นสุด!")
        else:
            with st.spinner("Creating task..."):
                res = create_task(new_task_title, new_task_desc, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"))
                if res.status_code == 201:
                    st.success("Task created successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to create task. Error: {res.status_code}")
