import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="BuildPM | Professional View", layout="wide", page_icon="🏗️")

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

# ==========================================
# 4. Data Processing (ดึงและเตรียมข้อมูลก่อน)
# ==========================================
tasks = get_tasks()
issues_only = [t for t in tasks if 'pull_request' not in t]

df = pd.DataFrame()
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
    # เรียงลำดับตามวันที่เริ่ม และ Reset Index ให้แถวตรงกับกราฟ
    df = df.sort_values("_raw_start").reset_index(drop=True)

# หาค่า Target Date พื้นฐานจากวันจบโปรเจกต์ที่ไกลที่สุด
default_target = df["FINISH"].max() if not df.empty else TODAY_DATE + timedelta(days=30)

# ==========================================
# 5. UI: Top Toolbar
# ==========================================
st.markdown("### 🏗️ BuildPM - Project Management Suite")

# ปรับคอลัมน์ด้านบนเพื่อเพิ่มที่เลือกวันที่ TARGET
t_col1, t_col2, t_col3, t_col4, t_col5 = st.columns([2.5, 1.5, 1.5, 1.5, 1])
with t_col1:
    search_query = st.text_input("🔍 Search tasks...", placeholder="พิมพ์ชื่อ Task...")
with t_col2:
    display_view = st.selectbox("☷ DISPLAY VIEW", ["Split-View (PM Style)", "Kanban Board"])
with t_col3:
    task_filter = st.selectbox("▽ FILTER STATUS", ["All Tasks", "IN PROGRESS", "DELAY", "COMPLETED"])
with t_col4:
    # เพิ่ม Date Input ให้คนใช้เปลี่ยนเส้น TARGET แดงๆ ได้เอง
    target_date = st.date_input("🎯 TARGET DATE", value=default_target)
with t_col5:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Sync", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ==========================================
# 6. Apply Filters & Render View
# ==========================================
if not df.empty:
    # กรองข้อมูลตามที่เลือกจาก Toolbar
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
    if task_filter != "All Tasks":
        df = df[df["STATUS"] == task_filter]
        
    df_display = df.drop(columns=["_raw_start", "_raw_body"])

    if not df.empty:
        if display_view == "Split-View (PM Style)":
            
            # คำนวณความสูงแบบไดนามิก ป้องกัน Scroll bar ซ้อน
            ROW_HEIGHT = 35
            DYNAMIC_HEIGHT = max(300, (len(df) * ROW_HEIGHT) + 42)

            # แบ่งครึ่งหน้าจอ (ซ้าย 45% : ขวา 55%)
            left_col, right_col = st.columns([0.45, 0.55])
            
            with left_col:
                # ----------------------------------
                # [ฝั่งซ้าย] Data Editor (ตารางข้อมูล)
                # ----------------------------------
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
                # ----------------------------------
                # [ฝั่งขวา] Plotly Gantt Chart
                # ----------------------------------
                fig = px.timeline(
                    df, 
                    x_start="START", 
                    x_end="FINISH", 
                    y="TASK NAME", 
                    color="STATUS",
                    color_discrete_map={
                        "COMPLETED": "#b5e5c5", 
                        "IN PROGRESS": "#cde0f5", 
                        "DELAY": "#f5cdcd"  
                    }
                )
                
                # ซ่อนแกน Y กลับด้านให้อิงกับตาราง
                fig.update_yaxes(autorange="reversed", visible=False, showgrid=False)
                
                # ตั้งค่าแกน X ให้อยู่ด้านบน
                fig.update_xaxes(
                    side="top", 
                    title=None,
                    tickformat="%d %b\n%a", 
                    showgrid=True, gridcolor='rgba(200, 200, 200, 0.3)',
                    dtick="86400000" # ขีดบอกทุกๆ 1 วัน
                )
                
                # --- เพิ่มเส้น CUT-OFF (เส้นประ) ---
                fig.add_vline(
                    x=TODAY_DATE, 
                    line_width=2, 
                    line_dash="dash", 
                    line_color="#5D3FD3", 
                    annotation_text="CUT-OFF", 
                    annotation_position="top left",
                    annotation=dict(font_size=10, font_color="white", bgcolor="#5D3FD3", borderpad=3, bordercolor="white", borderwidth=1)
                )

                # --- เพิ่มเส้น TARGET (เส้นทึบ) ---
                fig.add_vline(
                    x=target_date, 
                    line_width=2, 
                    line_dash="solid", 
                    line_color="#E3242B", 
                    annotation_text="TARGET", 
                    annotation_position="top right",
                    annotation=dict(font_size=10, font_color="white", bgcolor="#E3242B", borderpad=3, bordercolor="white", borderwidth=1)
                )
                
                # จัด Layout
                fig.update_layout(
                    margin=dict(l=0, r=0, t=50, b=0), # เว้นที่ให้ Annotation ข้างบน
                    height=DYNAMIC_HEIGHT,
                    showlegend=False,
                    plot_bgcolor="white"
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            # ----------------------------------
            # 7. 2-Way Sync Logic (อัปเดตกลับ GitHub)
            # ----------------------------------
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

        elif display_view == "Kanban Board":
            st.markdown("### 🗂️ Project Kanban Board")
            st.info("กำลังแสดงผลแบบ Gantt Chart กรุณาเลือก Split-View จากด้านบนเพื่อดูตารางเวลา")
            # ถ้าอยากใส่ Kanban แบบในโค้ดเดิม สามารถแทรกเข้ามาตรงนี้ได้เลยครับ

    else:
        st.warning("ไม่พบข้อมูลที่ตรงกับเงื่อนไขการค้นหา/ตัวกรอง")
else:
    st.info("ไม่มีงานในระบบ ปรับตั้งค่า GitHub หรือสร้าง Issue เพื่อเริ่มต้น")
