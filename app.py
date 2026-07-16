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
    st.error("Missing credentials in Streamlit Secrets.")
    st.stop()

def get_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# --- Data Fetching & Parsing ---
@st.cache_data(ttl=60) # Cache ข้อมูล 1 นาทีเพื่อให้แอปลื่นขึ้น
def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state=all"
    response = requests.get(url, headers=get_headers())
    return response.json() if response.status_code == 200 else []

def parse_dates_from_body(body, created_at):
    match = re.search(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", str(body))
    if match:
        return match.group(1), match.group(2)
    start = created_at[:10]
    end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=5)).strftime("%Y-%m-%d")
    return start, end

# วันที่ปัจจุบัน (จำลองตามระบบ)
TODAY = datetime(2026, 7, 16)

# --- UI: Top Toolbar (เลียนแบบในภาพ) ---
st.markdown("### 🏗️ BuildPM - Project Schedule")

t_col1, t_col2, t_col3, t_col4 = st.columns([3, 1, 1, 2])
with t_col1:
    search_query = st.text_input("🔍 Search tasks...", placeholder="พิมพ์ชื่อ Task...")
with t_col2:
    st.selectbox("☷ DISPLAY", ["Standard", "Expanded"])
with t_col3:
    st.selectbox("▽ FILTER", ["All Tasks", "Delayed", "In Progress"])
with t_col4:
    st.button("⚙️ MORE / SETTINGS")

st.markdown("---")

# --- Data Processing ---
tasks = get_tasks()
issues_only = [t for t in tasks if 'pull_request' not in t]

if issues_only:
    df_data = []
    for i, task in enumerate(issues_only):
        start_str, end_str = parse_dates_from_body(task.get('body'), task.get('created_at'))
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        
        # คำนวณจำนวนวัน (DAYS)
        days = (end_date - start_date).days + 1
        
        # ตรวจสอบสถานะ (เลียนแบบในภาพ: DELAY, ON TIME, COMPLETED)
        state = task.get('state')
        if state == 'closed':
            status = "COMPLETED"
        elif TODAY > end_date:
            status = "DELAY"
        else:
            status = "IN PROGRESS"
            
        # สร้างข้อมูล % PLAN แบบสุ่มให้ดูสมจริง (สำหรับตัวอย่าง)
        plan_pct = min(100.0, max(0.0, ((TODAY - start_date).days / days) * 100)) if days > 0 else 0
        act_pct = 100.0 if status == "COMPLETED" else (plan_pct * 0.5 if status == "DELAY" else plan_pct * 0.9)

        df_data.append({
            "ID": task['number'],
            "WBS": str(i+1),
            "TASK NAME": task['title'],
            "START": start_str,
            "FINISH": end_str,
            "DAYS": days,
            "% PLAN": f"{plan_pct:.2f}%",
            "% ACT.": f"{act_pct:.2f}%",
            "STATUS": status,
            "_raw_start": start_date # ซ่อนไว้ใช้เรียงลำดับ
        })
    
    df = pd.DataFrame(df_data)
    
    # กรองข้อมูลตามช่อง Search
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
        
    # เรียงลำดับตามวันที่เริ่มงาน
    df = df.sort_values("_raw_start").reset_index(drop=True)
    df_display = df.drop(columns=["_raw_start"])

    # ==========================================
    # 🗂️ ส่วนแสดงผล: แบ่งครึ่งจอซ้ายขวา
    # ==========================================
    col_left, col_right = st.columns([1.2, 1.5]) # อัตราส่วนความกว้าง
    
    with col_left:
        st.markdown("**📋 Task Details**")
        # ใช้ st.dataframe พร้อมตั้งค่าสีของคอลัมน์ STATUS
        st.dataframe(
            df_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "STATUS": st.column_config.TextColumn(
                    "STATUS", help="สถานะปัจจุบัน",
                    # ไฮไลต์สีข้อความ (เฉพาะ Streamlit เวอร์ชันใหม่ๆ)
                )
            },
            height=400 # กำหนดความสูงตารางให้เท่ากับกราฟ
        )
        
    with col_right:
        st.markdown("**📅 Gantt Chart Timeline**")
        # สร้างกราฟแกนต์และจัดเรียงให้ตรงกับตารางด้านซ้าย
        fig = px.timeline(
            df, 
            x_start="START", 
            x_end="FINISH", 
            y="TASK NAME", 
            color="STATUS",
            color_discrete_map={
                "COMPLETED": "#00C853",  # เขียว
                "IN PROGRESS": "#29B6F6", # ฟ้า
                "DELAY": "#FF5252"        # แดง (เหมือนในรูป)
            },
            hover_data=["DAYS", "% PLAN", "% ACT."]
        )
        # ตั้งค่ากราฟให้ดูสะอาดตาเหมือนในภาพ
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(title=None, side="top") # ย้ายวันที่ไปไว้ด้านบน
        fig.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            height=400, # ความสูงเท่ากับตาราง
            showlegend=False # ซ่อน Legend เพื่อประหยัดพื้นที่
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

else:
    st.info("ไม่มีงานในระบบ กดแถบด้านข้างเพื่อสร้างงานใหม่")

# --- Sidebar สำหรับสร้างงานใหม่ ---
with st.sidebar:
    st.header("➕ Create New Task")
    with st.form("new_task_form", clear_on_submit=True):
        new_task_title = st.text_input("Task Name")
        start_d = st.date_input("Start Date", value=TODAY)
        end_d = st.date_input("Finish Date", value=TODAY + timedelta(days=5))
        new_task_desc = st.text_area("Description")
        
        submitted = st.form_submit_button("Submit Task", type="primary", use_container_width=True)
        if submitted:
            if start_d > end_d:
                st.error("วันที่เริ่มต้องมาก่อนวันสิ้นสุด!")
            elif not new_task_title:
                st.warning("กรุณาใส่ชื่องาน")
            else:
                # Logic สร้างงาน API (ใช้โค้ดเดิมของคุณ)
                url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
                body = f"📅 **Timeline:** {start_d.strftime('%Y-%m-%d')} to {end_d.strftime('%Y-%m-%d')}\n\n{new_task_desc}"
                res = requests.post(url, headers=get_headers(), json={"title": new_task_title, "body": body})
                if res.status_code == 201:
                    st.success("สร้างงานสำเร็จ!")
                    st.cache_data.clear() # ล้างแคชเพื่อให้เห็นข้อมูลใหม่ทันที
                    st.rerun()
