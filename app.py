import streamlit as st
import requests
import pandas as pd
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
    # ตัวกรองสถานะที่ใช้งานได้จริง
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
        
        state = task.get('state')
        if state == 'closed':
            status = "COMPLETED"
        elif TODAY > end_date:
            status = "DELAY"
        else:
            status = "IN PROGRESS"
            
        assignees = ", ".join([a['login'] for a in task.get('assignees', [])]) if task.get('assignees') else "Unassigned"
        labels = ", ".join([l['name'] for l in task.get('labels', [])])
            
        plan_pct = min(100.0, max(0.0, ((TODAY - start_date).days / days) * 100)) if days > 0 else 0
        act_pct = calc_progress_from_checklist(body, status)

        df_data.append({
            "ID": task['number'],
            "WBS": str(i+1),
            "TASK NAME": task['title'],
            "ASSIGNEE": assignees,
            "START": start_date.date(),
            "FINISH": end_date.date(),
            "DAYS": days,
            "% PLAN": plan_pct,
            "% ACT.": act_pct, 
            "STATUS": status,
            "LABELS": labels,
            "_raw_start": start_date,
            "_raw_body": body 
        })
    
    df = pd.DataFrame(df_data)
    
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
    if task_filter != "All Tasks":
        df = df[df["STATUS"] == task_filter]
        
    df = df.sort_values("_raw_start").reset_index(drop=True)
    
    # เอา _raw_body ออกก่อนนำไปแสดงผลในตาราง
    df_display = df.drop(columns=["_raw_start", "_raw_body"])

    # ==========================================
    # 🗂️ ส่วนแสดงผล: ตารางเดียวเต็มจอ (รวม Gantt ไว้ในคอลัมน์)
    # ==========================================
    if not df.empty:
        # คำนวณช่วงเวลาทั้งหมดเพื่อทำ Mini Gantt
        min_date = df_display["START"].min()
        max_date = df_display["FINISH"].max()
        total_project_days = max(1, (max_date - min_date).days)
        
        def generate_mini_gantt(start, finish, status):
            TOTAL_BLOCKS = 20
            start_offset = (start - min_date).days
            duration = (finish - start).days
            
            bar_len = max(1, int(round((duration / total_project_days) * TOTAL_BLOCKS)))
            blank_before = min(TOTAL_BLOCKS - bar_len, int(round((start_offset / total_project_days) * TOTAL_BLOCKS)))
            blank_after = max(0, TOTAL_BLOCKS - blank_before - bar_len)
            
            if status == "COMPLETED": bar_char = "🟩"
            elif status == "DELAY": bar_char = "🟥"
            else: bar_char = "🟦"
                
            return "⬜" * blank_before + bar_char * bar_len + "⬜" * blank_after

        # เพิ่มคอลัมน์ GANTT TIMELINE
        df_display.insert(6, "TIMELINE", df_display.apply(
            lambda x: generate_mini_gantt(x["START"], x["FINISH"], x["STATUS"]), axis=1
        ))

        dynamic_height = max(400, len(df) * 38 + 50)
        
        st.markdown("**📋 Project Master Table** *(สามารถแก้ไขวันที่และสถานะในตารางได้โดยตรง)*")
        
        # ตารางเดียวเต็มจอ
        edited_df = st.data_editor(
            df_display,
            key="task_editor",
            hide_index=True,
            use_container_width=True,
            height=dynamic_height,
            column_config={
                "STATUS": st.column_config.SelectboxColumn("STATUS", options=["IN PROGRESS", "DELAY", "COMPLETED"]),
                "START": st.column_config.DateColumn("START", format="YYYY-MM-DD"),
                "FINISH": st.column_config.DateColumn("FINISH", format="YYYY-MM-DD"),
                "% PLAN": st.column_config.ProgressColumn("% PLAN", format="%.0f%%", min_value=0, max_value=100),
                "% ACT.": st.column_config.ProgressColumn("% ACT.", format="%.0f%%", min_value=0, max_value=100),
                "TIMELINE": st.column_config.TextColumn("GANTT TIMELINE", help="สีเขียว=เสร็จ, สีฟ้า=กำลังทำ, สีแดง=ล่าช้า")
            }
        )

        # ==========================================
        # ⚙️ 2-Way Sync: ตรวจจับการแก้ไขและยิง API อัปเดต GitHub
        # ==========================================
        if st.session_state.task_editor["edited_rows"]:
            st.toast('กำลังบันทึกข้อมูลไปที่ GitHub...', icon='🔄')
            
            # ดึงข้อมูลแถวที่มีการแก้ไข
            edits = st.session_state.task_editor["edited_rows"]
            
            for row_idx, changes in edits.items():
                issue_id = df["ID"].iloc[row_idx]
                current_body = df["_raw_body"].iloc[row_idx]
                
                payload = {}
                
                # 1. กรณีผู้ใช้เปลี่ยน STATUS (Completed -> ปิดงาน / อื่นๆ -> เปิดงาน)
                if "STATUS" in changes:
                    new_status = changes["STATUS"]
                    payload["state"] = "closed" if new_status == "COMPLETED" else "open"
                    
                # 2. กรณีผู้ใช้แก้ไขวันที่ START หรือ FINISH (ต้องไป Rewrite วันที่ใน Body)
                if "START" in changes or "FINISH" in changes:
                    # ดึงวันที่ใหม่ (ถ้าเปลี่ยนแค่วันเดียว ให้ใช้อีกวันจากข้อมูลเดิม)
                    new_start = str(changes.get("START", df_display["START"].iloc[row_idx]))
                    new_finish = str(changes.get("FINISH", df_display["FINISH"].iloc[row_idx]))
                    
                    # ค้นหาและแทนที่ Timeline เดิมใน Body
                    if re.search(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", current_body):
                        new_body = re.sub(
                            r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}",
                            f"📅 **Timeline:** {new_start} to {new_finish}",
                            current_body
                        )
                    else:
                        new_body = f"📅 **Timeline:** {new_start} to {new_finish}\n\n{current_body}"
                    
                    payload["body"] = new_body

                # 3. ยิง API PATCH กลับไปที่ GitHub
                if payload:
                    update_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}"
                    res = requests.patch(update_url, headers=get_headers(), json=payload)
                    if res.status_code != 200:
                        st.error(f"อัปเดตงาน #{issue_id} ไม่สำเร็จ")
            
            # เมื่อทำงานเสร็จ ให้ล้างแคชเพื่อให้โหลดข้อมูลใหม่ล่าสุดมาโชว์ และ Rerun จอ
            st.cache_data.clear()
            st.rerun()

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
            selected_task = st.selectbox("เลือกงานที่ต้องการอัปเดต (หรือแก้ในตารางได้เลย)", task_list)
            
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
