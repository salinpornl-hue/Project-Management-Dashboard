import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta, time

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="BuildPM | Project Management Dashboard", layout="wide", page_icon="🏗️")

# Custom CSS for UI layout cleanup
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    div[data-testid="stNotification"] { padding: 0.75rem; margin-bottom: 1rem; }
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
    # Fetch only open issues to keep active management organized
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
        gantt_cutoff = datetime.combine(cut_off_date, time(23, 59, 59))
        
        if gantt_finish <= gantt_cutoff:
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": gantt_start, "FINISH": gantt_finish, "STAGE": "Elapsed", "_raw_start": start_date})
        elif gantt_start > gantt_cutoff:
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": gantt_start, "FINISH": gantt_finish, "STAGE": "Future", "_raw_start": start_date})
        else:
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": gantt_start, "FINISH": gantt_cutoff, "STAGE": "Elapsed", "_raw_start": start_date})
            gantt_data.append({"UNIQUE_TASK": unique_name, "TASK NAME": task['title'], "START": gantt_cutoff, "FINISH": gantt_finish, "STAGE": "Future", "_raw_start": start_date})

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
# 7. UI: Bulk Edit Save Button & Zoom Controls
# ==========================================
st.markdown("##### 🔎 View & Editing Controls")
z_col1, z_col2, z_col3 = st.columns([1.5, 1.5, 4])

default_view_start = df["START"].min() - timedelta(days=2) if not df.empty else TODAY_DATE
default_view_end = df["FINISH"].max() + timedelta(days=2) if not df.empty else TODAY_DATE + timedelta(days=30)

with z_col1:
    view_start = st.date_input("🗓️ Zoom View From", value=default_view_start)
with z_col2:
    view_end = st.date_input("🗓️ Zoom View To", value=default_view_end)

# Bulk Change tracking mechanisms via Streamlit State
pending_changes = st.session_state.get("task_editor", {})
edited_rows = pending_changes.get("edited_rows", {})
added_rows = pending_changes.get("added_rows", [])
deleted_rows = pending_changes.get("deleted_rows", [])

total_changes = len(edited_rows) + len(added_rows) + len(deleted_rows)

if total_changes > 0:
    with z_col3:
        st.warning(f"⚠️ You have {total_changes} unsaved modifications pending.")
        if st.button("💾 Save Changes to GitHub", type="primary"):
            has_error = False
            
            with st.spinner("Syncing data updates with GitHub..."):
                # 1. Processing Row Deletions (Closing Items)
                for row_idx in deleted_rows:
                    issue_id = df["ID"].iloc[row_idx]
                    requests.patch(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}", headers=get_headers(), json={"state": "closed"})

                # 2. Processing Row Additions (New Issues)
                for new_row in added_rows:
                    title = new_row.get("TASK NAME", "Untitled Task")
                    start = str(new_row.get("START", TODAY_DATE.strftime("%Y-%m-%d")))
                    finish = str(new_row.get("FINISH", TODAY_DATE.strftime("%Y-%m-%d")))
                    assignee_str = str(new_row.get("ASSIGNEE", ""))
                    
                    body = f"📅 **Timeline:** {start} to {finish}\n\n- [ ] Checklist 1"
                    payload = {"title": title, "body": body}
                    
                    if assignee_str.strip():
                        payload["assignees"] = [a.strip() for a in assignee_str.split(",") if a.strip()]
                        
                    requests.post(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues", headers=get_headers(), json=payload)

                # 3. Processing Column Modifications
                for row_idx, changes in edited_rows.items():
                    if row_idx in deleted_rows:
                        continue
                        
                    issue_id = df["ID"].iloc[row_idx]
                    current_body = df["_raw_body"].iloc[row_idx]
                    current_title = df["TASK NAME"].iloc[row_idx]
                    payload = {}
                    
                    if "TASK NAME" in changes:
                        payload["title"] = changes["TASK NAME"]
                        
                    if "ASSIGNEE" in changes:
                        assignee_str = changes["ASSIGNEE"]
                        payload["assignees"] = [a.strip() for a in assignee_str.split(",") if a.strip()]
                        
                    if "START" in changes or "FINISH" in changes:
                        new_start_str = str(changes.get("START", df["START"].iloc[row_idx]))
                        new_finish_str = str(changes.get("FINISH", df["FINISH"].iloc[row_idx]))
                        
                        n_start_date = datetime.strptime(new_start_str, "%Y-%m-%d").date()
                        n_finish_date = datetime.strptime(new_finish_str, "%Y-%m-%d").date()
                        
                        if n_finish_date < n_start_date:
                            st.error(f"❌ Validation Failed: Task '{current_title}' has a Finish Date set before its Start Date!")
                            has_error = True
                            continue
                        
                        if re.search(r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", current_body):
                            payload["body"] = re.sub(
                                r"📅 \*\*Timeline:\*\* \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}",
                                f"📅 **Timeline:** {new_start_str} to {new_finish_str}", current_body)
                        else:
                            payload["body"] = f"📅 **Timeline:** {new_start_str} to {new_finish_str}\n\n{current_body}"

                    if payload and not has_error:
                        requests.patch(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_id}", headers=get_headers(), json=payload)
            
            if not has_error:
                st.success("✅ Dashboard configuration synchronized perfectly!")
                st.cache_data.clear()
                st.rerun()

# ==========================================
# 8. Render Split-View UI
# ==========================================
st.info("💡 **Tip:** Use the table footer controls (`+` icon) to add rows. Select any row and press `Delete` on your keyboard to drop a task.")

df_display = df.drop(columns=["UNIQUE_TASK", "_raw_start", "_raw_body"]) if not df.empty else pd.DataFrame(columns=["ID", "ASSIGNEE", "TASK NAME", "START", "FINISH", "DAYS", "% PLAN", "% ACT.", "STATUS", "% FUT"])

ROW_HEIGHT = 35.5 
HEADER_HEIGHT = 43 
EXACT_HEIGHT = int((len(df_display) * ROW_HEIGHT) + HEADER_HEIGHT) if len(df_display) > 0 else 150

left_col, right_col = st.columns([0.45, 0.55])

with left_col:
    edited_df = st.data_editor(
        df_display,
        key="task_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        height=EXACT_HEIGHT if len(df_display) > 0 else None,
        column_config={
            "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "ASSIGNEE": st.column_config.TextColumn("ASSIGNEE", disabled=False, width="small", help="GitHub usernames separated by a comma (,)"),
            "TASK NAME": st.column_config.TextColumn("TASK NAME", disabled=False, width="medium"),
            "START": st.column_config.DateColumn("START", disabled=False, format="DD MMM YYYY"), 
            "FINISH": st.column_config.DateColumn("FINISH", disabled=False, format="DD MMM YYYY"), 
            "DAYS": st.column_config.NumberColumn("DAYS", disabled=True),
            "% PLAN": st.column_config.ProgressColumn("% PLAN", format="%.2f%%", min_value=0, max_value=100),
            "% ACT.": st.column_config.ProgressColumn("% ACT.", format="%.2f%%", min_value=0, max_value=100),
            "STATUS": st.column_config.TextColumn("STATUS", disabled=True),
            "% FUT": st.column_config.ProgressColumn("% FUT", format="%.2f%%", min_value=0, max_value=100),
        }
    )

with right_col:
    if not df_gantt.empty:
        fig = px.timeline(
            df_gantt, 
            x_start="START", 
            x_end="FINISH", 
            y="UNIQUE_TASK", 
            color="STAGE",
            color_discrete_map={
                "Elapsed": "#cde0f5", 
                "Future": "#e8f5e9",  
            }
        )
        
        fig.update_traces(marker_line_color='rgba(100, 120, 150, 0.5)', marker_line_width=1, opacity=0.9)
        
        ordered_tasks = df["UNIQUE_TASK"].tolist()
        fig.update_yaxes(autorange="reversed", categoryorder='array', categoryarray=ordered_tasks, visible=False, showgrid=False)
        
        fig.update_xaxes(
            side="top", 
            title=None,
            tickformat="%d %b\n%a", 
            showgrid=True, gridcolor='rgba(200, 200, 200, 0.3)',
            dtick="86400000",
            range=[view_start.strftime("%Y-%m-%d"), view_end.strftime("%Y-%m-%d")]
        )
        
        fig.add_vline(x=cut_off_date.strftime("%Y-%m-%d 23:59:59"), line_width=2, line_dash="dash", line_color="#5D3FD3", annotation_text="CUT-OFF", annotation_position="top left", annotation=dict(font_size=10, font_color="white", bgcolor="#5D3FD3", borderpad=2, bordercolor="white"))
        fig.add_vline(x=target_date.strftime("%Y-%m-%d 23:59:59"), line_width=2, line_dash="solid", line_color="#E3242B", annotation_text="TARGET", annotation_position="top right", annotation=dict(font_size=10, font_color="white", bgcolor="#E3242B", borderpad=2, bordercolor="white"))
        
        fig.update_layout(
            margin=dict(l=0, r=0, t=HEADER_HEIGHT, b=0),
            height=EXACT_HEIGHT,
            showlegend=False,
            plot_bgcolor="white"
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.markdown("<div style='text-align: center; color: gray; margin-top: 50px;'>No timeline metrics matching criteria.</div>", unsafe_allow_html=True)
