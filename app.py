import streamlit as st
import requests

# 1. Page Configuration
st.set_page_config(page_title="BuildPM Task Tracker", layout="wide")

# 2. Load Secrets securely
try:
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception as e:
    st.error("Configuration Error: Missing credentials. Please configure GITHUB_TOKEN, REPO_OWNER, and REPO_NAME in Streamlit Secrets.")
    st.stop()

# --- Functions สำหรับติดต่อ API ---

# ฟังก์ชันดึงข้อมูลงาน (GET)
def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        st.error("Error 401 (Unauthorized): Invalid GitHub Token. Please verify your credentials in Streamlit Secrets.")
        return []
    elif response.status_code == 404:
        st.error("Error 404 (Not Found): Repository not found. Please check your REPO_OWNER and REPO_NAME.")
        return []
    else:
        st.error(f"Failed to fetch data. API returned status code: {response.status_code}")
        return []

# ฟังก์ชันสร้างงานใหม่ (POST)
def create_task(title, body):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "title": title,
        "body": body
    }
    response = requests.post(url, headers=headers, json=payload)
    return response

# --- UI และการแสดงผล ---

st.title("🏗️ BuildPM - Project Management System")
st.write("Project tracking and task handover dashboard")

# Fetch data
tasks = get_tasks()

if not tasks:
    st.info("No tasks found in the system, or the repository configuration is incorrect.")
else:
    # Task Rendering Layout
    cols = st.columns(3)
    
    for task in tasks:
        # ข้าม Pull Requests
        if 'pull_request' in task:
            continue
            
        title = task.get('title', 'Untitled Task')
        body = task.get('body', 'No description provided.')
        assignee = task.get('assignee', {}).get('login', 'Unassigned') if task.get('assignee') else 'Unassigned'
        labels = [label['name'] for label in task.get('labels', [])]
        
        # แสดงผล
        with st.expander(f"📌 {title} | Assignee: {assignee}"):
            st.markdown(f"**Description:** \n{body}")
            st.write(f"**Status:** {', '.join(labels) if labels else 'No status'}")
            
            if st.button("Handover Task", key=f"btn_{task['id']}"):
                st.success(f"Task '{title}' has been successfully handed over!")

# --- Sidebar สำหรับสร้างงานใหม่ ---
with st.sidebar:
    st.header("➕ Create New Task")
    new_task_title = st.text_input("Task Title")
    new_task_desc = st.text_area("Task Description")
    
    if st.button("Create Task", type="primary"):
        if not new_task_title.strip():
            st.warning("Please enter a Task Title.")
        else:
            with st.spinner("Creating task..."):
                res = create_task(new_task_title, new_task_desc)
                if res.status_code == 201: # 201 คือ Created (สร้างสำเร็จ)
                    st.success("Task created successfully! Please refresh the page.")
                    # หากรันบนเครื่องตัวเองสามารถใช้ st.experimental_rerun() ได้
                else:
                    st.error(f"Failed to create task. Error: {res.status_code}")
                    st.write(res.text) # แสดงข้อความ error จาก GitHub เพื่อช่วยหาจุดบกพร่อง
