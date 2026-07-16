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

# 3. Fetch Tasks from GitHub API
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

# 4. Main Dashboard UI
st.title("🏗️ BuildPM - Project Management System")
st.write("Project tracking and task handover dashboard")

# Fetch data
tasks = get_tasks()

if not tasks:
    st.info("No tasks found in the system, or the repository configuration is incorrect.")
else:
    # 5. Task Rendering Layout
    cols = st.columns(3)
    
    for task in tasks:
        # Skip Pull Requests (GitHub API includes PRs in the Issues endpoint)
        if 'pull_request' in task:
            continue
            
        title = task.get('title', 'Untitled Task')
        body = task.get('body', 'No description provided.')
        assignee = task.get('assignee', {}).get('login', 'Unassigned') if task.get('assignee') else 'Unassigned'
        labels = [label['name'] for label in task.get('labels', [])]
        
        # Display each task inside an expander
        with st.expander(f"📌 {title} | Assignee: {assignee}"):
            st.markdown(f"**Description:** \n{body}")
            st.write(f"**Status:** {', '.join(labels) if labels else 'No status'}")
            
            # Workflow Handover Button
            if st.button("Handover Task", key=f"btn_{task['id']}"):
                st.success(f"Task '{title}' has been successfully handed over!")
                # Insert POST request logic here for actual state updates

# 6. Sidebar for Creating New Tasks
with st.sidebar:
    st.header("➕ Create New Task")
    new_task_title = st.text_input("Task Title")
    new_task_desc = st.text_area("Task Description")
    if st.button("Create Task", type="primary"):
        st.warning("Task creation requires an active POST request setup with Write permissions.")
