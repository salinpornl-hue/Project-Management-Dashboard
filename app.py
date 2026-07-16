import streamlit as st
import requests

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

# --- Functions สำหรับติดต่อ API ---

def get_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

# ฟังก์ชันดึงข้อมูลงาน (GET)
def get_tasks():
    # ดึงเฉพาะ issue ที่ยังเปิดอยู่ (state=open)
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state=open"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        st.error("Error 401 (Unauthorized): Invalid GitHub Token.")
        return []
    elif response.status_code == 404:
        st.error("Error 404 (Not Found): Repository not found.")
        return []
    else:
        st.error(f"Failed to fetch data. API returned status code: {response.status_code}")
        return []

# ฟังก์ชันสร้างงานใหม่ (POST)
def create_task(title, body):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    payload = {"title": title, "body": body}
    return requests.post(url, headers=get_headers(), json=payload)

# ฟังก์ชันอัปเดตสถานะงาน (PATCH) เช่น ปิดงาน
def update_task_state(issue_number, state="closed"):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
    payload = {"state": state}
    return requests.patch(url, headers=get_headers(), json=payload)

# --- UI และการแสดงผล ---

st.title("🏗️ BuildPM - Project Management System")
st.write("Project tracking and task handover dashboard")
st.markdown("---")

# Fetch data
tasks = get_tasks()

if not tasks:
    st.info("🎉 No active tasks! Your team is all caught up, or the repository configuration is incorrect.")
else:
    # กรองเอาเฉพาะ Issue แท้ๆ (ไม่เอา Pull Request)
    issues_only = [t for t in tasks if 'pull_request' not in t]
    
    # Task Rendering Layout (จัดเรียง 3 คอลัมน์)
    cols = st.columns(3)
    
    for index, task in enumerate(issues_only):
        title = task.get('title', 'Untitled Task')
        body = task.get('body', 'No description provided.')
        assignee = task.get('assignee', {}).get('login', 'Unassigned') if task.get('assignee') else 'Unassigned'
        labels = [label['name'] for label in task.get('labels', [])]
        issue_number = task.get('number')
        
        # กระจายการ์ดงานลงคอลัมน์ (0, 1, 2 วนลูปไปเรื่อยๆ)
        col = cols[index % 3]
        
        with col:
            with st.container(border=True):
                st.markdown(f"#### 📌 {title}")
                st.caption(f"👤 Assignee: **{assignee}**")
                
                # ถ้ามี Label ให้แสดงผลด้วยสีเทา
                if labels:
                    st.write(f"🏷️ `{', '.join(labels)}`")
                    
                with st.expander("ดูรายละเอียดงาน"):
                    st.write(body)
                
                # แบ่งปุ่มกดเป็น 2 ฝั่ง
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    if st.button("ส่งต่องาน 🔄", key=f"handover_{issue_number}", use_container_width=True):
                        st.toast(f"จำลองการส่งต่องาน: {title}")
                
                with btn_col2:
                    if st.button("ปิดงาน ✅", key=f"close_{issue_number}", type="primary", use_container_width=True):
                        res = update_task_state(issue_number, "closed")
                        if res.status_code == 200:
                            st.success("ปิดงานเรียบร้อย!")
                            st.rerun() # รีเฟรชหน้าจออัตโนมัติ
                        else:
                            st.error(f"เกิดข้อผิดพลาด: {res.status_code}")

# --- Sidebar สำหรับสร้างงานใหม่ ---
with st.sidebar:
    st.header("➕ Create New Task")
    new_task_title = st.text_input("Task Title")
    new_task_desc = st.text_area("Task Description")
    
    if st.button("Create Task", type="primary", use_container_width=True):
        if not new_task_title.strip():
            st.warning("Please enter a Task Title.")
        else:
            with st.spinner("Creating task..."):
                res = create_task(new_task_title, new_task_desc)
                if res.status_code == 201:
                    st.success("Task created successfully!")
                    st.rerun() # รีเฟรชหน้าจออัตโนมัติเพื่อให้งานใหม่โผล่ขึ้นมาทันที
                else:
                    st.error(f"Failed to create task. Error: {res.status_code}")
                    st.write(res.text)
