import streamlit as st
import requests

# ... (ส่วนการตั้งค่า GITHUB_TOKEN เดิมของคุณ) ...

def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error: {response.status_code}")
        return []

tasks = get_tasks()

st.title("🏗️ Project Management Dashboard")

# ตรวจสอบว่า tasks เป็น list หรือไม่
if isinstance(tasks, list):
    for task in tasks:
        # ใช้ .get() เพื่อป้องกัน Key Error
        title = task.get('title', 'Untitled Task')
        
        # ตรวจสอบว่าเป็น Issue หรือไม่ (GitHub รวม PR ไว้ใน Issues API ด้วย)
        if 'pull_request' not in task: 
            with st.expander(f"Task: {title}"):
                # ปลอดภัยขึ้นด้วยการใช้ .get() กับทุกส่วน
                assignee = task.get('assignee')
                assignee_name = assignee.get('login') if assignee else 'ยังไม่มี'
                
                st.write(f"**สถานะ:** {task.get('state', 'N/A')}")
                st.write(f"**ผู้รับผิดชอบ:** {assignee_name}")
                st.write(f"**รายละเอียด:** {task.get('body', 'ไม่มีรายละเอียด')}")
else:
    st.warning("ไม่สามารถดึงข้อมูลจาก GitHub ได้ หรือไม่มีข้อมูลใน Repo")
