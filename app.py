import streamlit as st
import requests

# ตั้งค่า GitHub (ควรเก็บไว้ใน Streamlit Secrets)
GITHUB_TOKEN = "your_github_personal_access_token"
REPO_OWNER = "your_username"
REPO_NAME = "your_project_repo"

def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.json()

st.title("🏗️ Project Management Dashboard")

# ดึงข้อมูลมาแสดง
tasks = get_tasks()

for task in tasks:
    # แสดงรายละเอียดงานแบบ Kanban style
    with st.expander(f"Task: {task['title']}"):
        st.write(f"**สถานะ:** {task['state']}")
        st.write(f"**ผู้รับผิดชอบ:** {task['assignee']['login'] if task['assignee'] else 'ยังไม่มี'}")
        st.write(f"**รายละเอียด:** {task['body']}")
        
        # ส่วนส่งต่องาน (สร้างปุ่มจำลอง)
        if st.button(f"ส่งงานต่อให้คนถัดไป", key=task['id']):
            st.success("ส่งต่องานเรียบร้อยแล้ว!")
