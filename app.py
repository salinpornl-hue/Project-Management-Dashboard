import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="BuildPM | Advanced Split-View", layout="wide", page_icon="🏗️")

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

def calc_progress_from_checklist(body, state):
    if not body:
        return 100.0 if state == "closed" else 0.0
    checked = body.lower().count("[x]")
    unchecked = body.lower().count("[ ]")
    total = checked + unchecked
    if total > 0:
        return (checked / total) * 100
    return 100.0 if state == "closed" else 0.0

# ==========================================
# 4. Fetch Base Data
# ==========================================
tasks = get_tasks()
issues_only = [t for t in tasks if 'pull_request' not in t]

# ==========================================
# 5. UI: Top Toolbar (Main Controls)
# ==========================================
st.markdown("### 🏗️ BuildPM - Advanced Project Tracking")

t_col1, t_col2, t_col3, t_col4, t_col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
with t_col1:
    search_query = st.text_input("🔍 Search tasks...")
with t_col2:
    cut_off_date = st.date_input("✂️ CUT-OFF DATE", value=TODAY_DATE)
with t_col3:
    # คำนวณหา Target ชั่วคราวจากงานทั้งหมด (ถ้ามี)
    temp_target = TODAY_DATE + timedelta(days=30)
    if issues_only:
        dates = [parse_dates_from_body(t.get('body', ''), t.get('created_at'))[1] for t in issues_only]
        temp_target = datetime.strptime(max(dates), "%Y-%m-%d").date()
    target_date = st.date_input("🎯 TARGET DATE", value=temp_target)
with t_col4:
    task_filter = st.selectbox("▽ STATUS FILTER", ["All", "ON TRACK", "DELAY", "COMPLETED"])
with t_col5:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Sync GitHub", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ==========================================
# 6. Data Processing (คำนวณและสร้าง UNIQUE_TASK)
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
        
        total_days = (end_date - start_date).days + 1
        elapsed_days = (cut_off_date - start_date).days + 1
        
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

        # 💡 สร้าง UNIQUE_TASK เพื่อป้องกัน Plotly ยุบรวมแถวที่มีชื่อซ้ำกัน
        unique_name = f"{task['number']} - {task['title']}"

        # --- ชุดข้อมูลสำหรับตาราง (Table Data) ---
        df_data.append({
            "ID": task['number'],
            "UNIQUE_TASK": unique_name,
            "WBS": str(i+1),
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
        
        # --- ชุดข้อมูลสำหรับกราฟ (Gantt Data - การหั่น 2 สี) ---
        if end_date <= cut_off_date:
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": start_date, "FINISH": end_date, "STAGE": "Elapsed", "_raw_start": start_date})
        elif start_date > cut_off_date:
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": start_date, "FINISH": end_date, "STAGE": "Future", "_raw_start": start_date})
        else:
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": start_date, "FINISH": cut_off_date, "STAGE": "Elapsed", "_raw_start": start_date})
            next_day = cut_off_date + timedelta(days=1)
            if next_day <= end_date:
                gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": next_day, "FINISH": end_date, "STAGE": "Future", "_raw_start": start_date})

    # สรุป Dataframe และเรียงลำดับ
    df = pd.DataFrame(df_data).sort_values("_raw_start").reset_index(drop=True)
    df_gantt = pd.DataFrame(gantt_data).sort_values("_raw_start").reset_index(drop=True)
    
    # ใช้งาน Filter
    if search_query:
        df = df[df["TASK NAME"].str.contains(search_query, case=False)]
        df_gantt = df_gantt[df_gantt["TASK NAME"].str.contains(search_query, case=False)]
    if task_filter != "All":
        df = df[df["STATUS"] == task_filter]
        valid_tasks = df["UNIQUE_TASK"].tolist()
        df_gantt = df_gantt[df_gantt["UNIQUE_TASK"].isin(valid_tasks)]

# ==========================================
# 7. UI: Zoom Controls (Time-Axis Scaling)
# ==========================================
if not df.empty:
    st.markdown("##### 🔎 จัดการมุมมองเวลา (Zoom / Time Scaling)")
    z_col1, z_col2, z_col3 = st.columns([1, 1, 4])
    
    # ค่าเริ่มต้นสำหรับ Zoom: เอาวันที่เริ่มก่อนสุด และจบหลังสุดมาแสดง
    default_view_start = df["START"].min() - timedelta(days=2)
    default_view_end = df["FINISH"].max() + timedelta(days=2)
    
    with z_col1:
        view_start = st.date_input("🗓️ ซูมตั้งแต่ (View Start)", value=default_view_start)
    with z_col2:
        view_end = st.date_input("🗓️ จนถึง (View End)", value=default_view_end)

# ==========================================
# 8. Render Split-View UI
# ==========================================
if not df.empty:
    # ตัดคอลัมน์ที่ใช้ประมวลผลออก ก่อนแสดงในตาราง
    df_display = df.drop(columns=["UNIQUE_TASK", "_raw_start", "_raw_body"])

    ROW_HEIGHT = 35
    DYNAMIC_HEIGHT = max(300, (len(df) * ROW_HEIGHT) + 42)

    left_col, right_col = st.columns([0.45, 0.55])
    
    with left_col:
        # [ฝั่งซ้าย] Data Editor (ตารางข้อมูล)
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
                "% PLAN": st.column_config.ProgressColumn("% PLAN", format="%.2f%%", min_value=0, max_value=100),
                "% ACT.": st.column_config.ProgressColumn("% ACT.", format="%.2f%%", min_value=0, max_value=100),
                "STATUS": st.column_config.TextColumn("STATUS", disabled=True),
                "% FUT": st.column_config.ProgressColumn("% FUT", format="%.2f%%", min_value=0, max_value=100),
            }
        )

    with right_col:
        # [ฝั่งขวา] Plotly Gantt Chart
        fig = px.timeline(
            df_gantt, 
            x_start="START", 
            x_end="FINISH", 
            y="UNIQUE_TASK", # 💡 ใช้ UNIQUE_TASK เป็นแกน Y เพื่อไม่ให้รวมแถวซ้ำ
            color="STAGE",
            color_discrete_map={
                "Elapsed": "#cde0f5", 
                "Future": "#e8f5e9",  
            }
        )
        
        fig.update_traces(marker_line_color='rgba(100, 120, 150, 0.5)', marker_line_width=1, opacity=0.9)
        
        # 💡 บังคับให้เรียงแถวตามตารางเป๊ะๆ (จากบนลงล่าง)
        ordered_tasks = df["UNIQUE_TASK"].tolist()[::-1]
        fig.update_yaxes(categoryorder='array', categoryarray=ordered_tasks, visible=False, showgrid=False)
        
        # 💡 ใส่ระบบ Zoom (จำกัดช่วงเวลาแสดงผลตาม view_start, view_end)
        fig.update_xaxes(
            side="top", 
            title=None,
            tickformat="%d %b\n%a", 
            showgrid=True, gridcolor='rgba(200, 200, 200, 0.3)',
            dtick="86400000",
            range=[view_start.strftime("%Y-%m-%d"), view_end.strftime("%Y-%m-%d")]
        )
        
        # เส้น CUT-OFF 
        fig.add_vline(
            x=cut_off_date.strftime("%Y-%m-%d"), 
            line_width=2, 
            line_dash="dash", 
            line_color="#5D3FD3", 
            annotation_text="CUT-OFF", 
            annotation_position="top left",
            annotation=dict(font_size=10, font_color="white", bgcolor="#5D3FD3", borderpad=2, bordercolor="white")
        )

        # เส้น TARGET 
        fig.add_vline(
            x=target_date.strftime("%Y-%m-%d"), 
            line_width=2, 
            line_dash="solid", 
            line_color="#E3242B", 
            annotation_text="TARGET", 
            annotation_position="top right",
            annotation=dict(font_size=10, font_color="white", bgcolor="#E3242B", borderpad=2, bordercolor="white")
        )
        
        # 💡 ปรับ Margin บน (t=42) เพื่อชดเชยความสูงให้เท่ากับหัวตาราง Data Editor พอดี
        fig.update_layout(
            margin=dict(l=0, r=0, t=42, b=0),
            height=DYNAMIC_HEIGHT,
            showlegend=False,
            plot_bgcolor="white"
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # ==========================================
    # 9. 2-Way Sync Logic (อัปเดตกลับ GitHub)
    # ==========================================
    if st.session_state.task_editor["edited_rows"]:
        st.toast('กำลังซิงค์ข้อมูลกับ GitHub...', icon='🔄')
        edits = st.session_state.task_editor["edited_rows"]
        for row_idx, changes in edits.items():
            issue_id = df["ID"].iloc[row_idx]
            current_body = df["_raw_body"].iloc[row_idx]
            payload = {}
                
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

else:
    st.info("ไม่มีงานในระบบ ปรับตั้งค่า GitHub หรือสร้าง Issue เพื่อเริ่มต้น")
