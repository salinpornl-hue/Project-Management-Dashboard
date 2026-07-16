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

# ฟังก์ชัน Helper สำหรับเปลี่ยนสถานะงาน
def update_task_state(issue_id, new_state):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}"
    res = requests.patch(url, headers=get_headers(), json={"state": new_state})
    if res.status_code == 200:
        st.cache_data.clear()
        st.rerun()
    else:
        st.error("อัปเดตไม่สำเร็จ")

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

TODAY = datetime.now()

# --- UI: Top Toolbar ---
st.markdown("### 🏗️ BuildPM - Project Management Suite")

t_col1, t_col2, t_col3, t_col4 = st.columns([2.5, 1.5, 1.5, 1])
with t_col1:
    search_query = st.text_input("🔍 Search tasks...", placeholder="พิมพ์ชื่อ Task...")
with t_col2:
    # เพิ่มตัวเลือก DISPLAY มุมมองต่างๆ
    display_view = st.selectbox("☷ DISPLAY VIEW", ["Table & Gantt", "Kanban Board", "Dashboard Metrics"])
with t_col3:
    task_filter = st.selectbox("▽ FILTER STATUS", ["All Tasks", "IN PROGRESS", "DELAY", "COMPLETED"])
with t_col4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh"):
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
            
        plan_pct = min(100.0, max(0.0, ((TODAY - start_date).days / days) * 100)) if days > 0 else 0
        act_pct = calc_progress_from_checklist(body, status)

        # การใช้ % PLAN และ % ACT. ให้เกิดประโยชน์สูงสุด (หา Project Health)
        variance = act_pct - plan_pct
        if status == "COMPLETED":
            health = "🟢 Done"
        elif variance >= 0:
            health = "🟢 On Track"
        elif variance > -20:
            health = "🟡 At Risk"
        else:
            health = "🔴 Behind"

        df_data.append({
            "ID": task['number'],
            "TASK NAME": task['title'],
            "ASSIGNEE": assignees,
            "START": start_date.date(),
            "FINISH": end_date.date(),
            "DAYS": days,
            "% PLAN": plan_pct,
            "% ACT.": act_pct, 
            "HEALTH": health,  # คอลัมน์ใหม่
            "STATUS": status,
            "_raw_start": start_date,
            "_raw_body": body 
        })
    
    df = pd.DataFrame(df_data)
    
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
    if task_filter != "All Tasks":
        df = df[df["STATUS"] == task_filter]
        
    df = df.sort_values("_raw_start").reset_index(drop=True)
    df_display = df.drop(columns=["_raw_start", "_raw_body"])

    if not df.empty:
        # ==========================================
        # 1. VIEW: TABLE & GANTT (มุมมองตาราง 2-Way Sync)
        # ==========================================
        if display_view == "Table & Gantt":
            min_date = df_display["START"].min()
            max_date = df_display["FINISH"].max()
            total_project_days = max(1, (max_date - min_date).days)
            
            def generate_mini_gantt(start, finish, status):
                TOTAL_BLOCKS = 15
                start_offset = (start - min_date).days
                duration = (finish - start).days
                bar_len = max(1, int(round((duration / total_project_days) * TOTAL_BLOCKS)))
                blank_before = min(TOTAL_BLOCKS - bar_len, int(round((start_offset / total_project_days) * TOTAL_BLOCKS)))
                blank_after = max(0, TOTAL_BLOCKS - blank_before - bar_len)
                bar_char = "🟩" if status == "COMPLETED" else "🟥" if status == "DELAY" else "🟦"
                return "⬜" * blank_before + bar_char * bar_len + "⬜" * blank_after

            df_display.insert(6, "TIMELINE", df_display.apply(
                lambda x: generate_mini_gantt(x["START"], x["FINISH"], x["STATUS"]), axis=1
            ))

            st.markdown("**📋 Master Schedule** *(แก้ไขวันที่/สถานะในตารางเพื่อบันทึกไป GitHub อัตโนมัติ)*")
            
            edited_df = st.data_editor(
                df_display,
                key="task_editor",
                hide_index=True,
                use_container_width=True,
                height=max(400, len(df) * 38 + 50),
                column_config={
                    "STATUS": st.column_config.SelectboxColumn("STATUS", options=["IN PROGRESS", "DELAY", "COMPLETED"]),
                    "START": st.column_config.DateColumn("START", format="YYYY-MM-DD"),
                    "FINISH": st.column_config.DateColumn("FINISH", format="YYYY-MM-DD"),
                    "% PLAN": st.column_config.ProgressColumn("% PLAN", format="%.0f%%", min_value=0, max_value=100),
                    "% ACT.": st.column_config.ProgressColumn("% ACT.", format="%.0f%%", min_value=0, max_value=100),
                    "TIMELINE": st.column_config.TextColumn("GANTT", help="สีเขียว=เสร็จ, สีฟ้า=กำลังทำ, สีแดง=ล่าช้า")
                }
            )

            # 2-Way Sync Logic
            if st.session_state.task_editor["edited_rows"]:
                st.toast('กำลังอัปเดต GitHub...', icon='🔄')
                edits = st.session_state.task_editor["edited_rows"]
                for row_idx, changes in edits.items():
                    issue_id = df["ID"].iloc[row_idx]
                    current_body = df["_raw_body"].iloc[row_idx]
                    payload = {}
                    
                    if "STATUS" in changes:
                        payload["state"] = "closed" if changes["STATUS"] == "COMPLETED" else "open"
                        
                    if "START" in changes or "FINISH" in changes:
                        new_start = str(changes.get("START", df_display["START"].iloc[row_idx]))
                        new_finish = str(changes.get("FINISH", df_display["FINISH"].iloc[row_idx]))
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

        # ==========================================
        # 2. VIEW: KANBAN BOARD (บอร์ดสไตล์ Trello)
        # ==========================================
        elif display_view == "Kanban Board":
            st.markdown("### 🗂️ Project Kanban Board")
            col_todo, col_delay, col_done = st.columns(3)
            
            with col_todo:
                st.success("🟦 **IN PROGRESS (กำลังดำเนินการ)**")
                for _, row in df[df["STATUS"] == "IN PROGRESS"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"**#{row['ID']} {row['TASK NAME']}**")
                        st.caption(f"👤 {row['ASSIGNEE']} | 🗓️ {row['FINISH']}")
                        st.progress(row["% ACT."] / 100, text=f"Progress: {row['% ACT.']:.0f}%")
                        if st.button("✅ Mark as Done", key=f"kb_done_{row['ID']}", use_container_width=True):
                            update_task_state(row['ID'], "closed")
                            
            with col_delay:
                st.error("🟥 **DELAYED (ล่าช้ากว่ากำหนด)**")
                for _, row in df[df["STATUS"] == "DELAY"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"**#{row['ID']} {row['TASK NAME']}**")
                        st.caption(f"👤 {row['ASSIGNEE']} | ⚠️ Due: {row['FINISH']}")
                        st.progress(row["% ACT."] / 100, text=f"Progress: {row['% ACT.']:.0f}%")
                        if st.button("✅ Force Done", key=f"kb_fdone_{row['ID']}", use_container_width=True):
                            update_task_state(row['ID'], "closed")

            with col_done:
                st.info("🟩 **COMPLETED (เสร็จสมบูรณ์)**")
                for _, row in df[df["STATUS"] == "COMPLETED"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"~~**#{row['ID']} {row['TASK NAME']}**~~")
                        if st.button("↩️ Reopen", key=f"kb_reopen_{row['ID']}", use_container_width=True):
                            update_task_state(row['ID'], "open")

        # ==========================================
        # 3. VIEW: DASHBOARD (สรุปผลและกราฟ)
        # ==========================================
        elif display_view == "Dashboard Metrics":
            # แถว KPI บนสุด
            st.subheader("📊 Executive Summary")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Total Tasks", len(df))
            kpi2.metric("Completed", len(df[df["STATUS"] == "COMPLETED"]))
            kpi3.metric("Delayed", len(df[df["STATUS"] == "DELAY"]), delta_color="inverse")
            
            # คำนวณ Overall Progress ของโปรเจกต์
            avg_act = df["% ACT."].mean()
            kpi4.metric("Overall Project Progress", f"{avg_act:.1f}%")

            st.markdown("---")
            d_col1, d_col2 = st.columns([1, 1.5])
            
            with d_col1:
                st.markdown("**สถานะงานรวม (Task Breakdown)**")
                fig_pie = px.pie(df, names="STATUS", color="STATUS", 
                                 color_discrete_map={"COMPLETED": "#00C853", "IN PROGRESS": "#29B6F6", "DELAY": "#FF5252"}, hole=0.4)
                fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with d_col2:
                st.markdown("**เปรียบเทียบ % แผนงาน vs % ทำจริง (Plan vs Actual)**")
                # นำ % PLAN กับ % ACT มาสร้างกราฟแท่งเปรียบเทียบ
                fig_bar = px.bar(df, x="TASK NAME", y=["% PLAN", "% ACT."], barmode="group",
                                 labels={"value": "Percentage (%)", "variable": "Metric"})
                fig_bar.update_layout(margin=dict(t=0, b=0, l=0, r=0), legend=dict(title=None, orientation="h", y=1.1))
                st.plotly_chart(fig_bar, use_container_width=True)

    else:
        st.warning("ไม่พบข้อมูลที่ตรงกับเงื่อนไขการค้นหา/ตัวกรอง")
else:
    st.info("ไม่มีงานในระบบ กดแถบด้านข้างเพื่อสร้างงานใหม่")


# --- Sidebar: จัดการงาน ---
with st.sidebar:
    st.header("➕ Quick Action")
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
