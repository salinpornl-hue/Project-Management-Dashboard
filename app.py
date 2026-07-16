import streamlit as st
import requests

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="BuildPM Task Tracker", layout="wide")

# ดึงข้อมูลจาก Secrets (ปลอดภัยกว่าการเขียน Token ไว้ในโค้ด)
try:
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception as e:
    st.error("กรุณาตั้งค่า Secrets ใน Streamlit Cloud ก่อน (GITHUB_TOKEN, REPO_OWNER, REPO_NAME)")
    st.stop()

# ฟังก์ชันดึงงานจาก GitHub Issues
def get_tasks():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"ไม่สามารถดึงข้อมูลได้: {response.status_code}")
        return []

st.title("🏗️ BuildPM - Project Management System")
st.write("ระบบติดตามความคืบหน้าโครงการและส่งต่องาน")

# ดึงข้อมูล
tasks = get_tasks()

if not tasks:
    st.info("ยังไม่มีงานในระบบ หรือตั้งค่า Repo ไม่ถูกต้อง")
else:
    # สร้าง Dashboard แบบ Grid
    cols = st.columns(3)
    
    # แยกสถานะงานตาม Label (สมมติใช้ Label ใน GitHub)
    for task in tasks:
        # ข้ามถ้าเป็น Pull Request
        if 'pull_request' in task:
            continue
            
        title = task.get('title', 'Untitled')
        body = task.get('body', 'ไม่มีรายละเอียด')
        assignee = task.get('assignee', {}).get('login', 'ยังไม่มีคนรับผิดชอบ')
        labels = [label['name'] for label in task.get('labels', [])]
        
        # แสดงผลใน Expander
        with st.expander(f"📌 {title} | ใครทำ: {assignee}"):
            st.write(f"**รายละเอียด:** {body}")
            st.write(f"**สถานะ:** {', '.join(labels) if labels else 'ไม่มีสถานะ'}")
            
            # ปุ่มส่งต่องาน (จำลอง Workflow)
            if st.button("ส่งต่องานให้คนถัดไป", key=task['id']):
                st.success(f"บันทึกการส่งงานเรียบร้อย: {title}")
                # ตรงนี้คุณสามารถเพิ่ม Logic การเรียก API เพื่ออัปเดต Label หรือ Assignee ต่อไปได้

# ส่วนเพิ่มงานใหม่ (Side Bar)
with st.sidebar:
    st.header("➕ เพิ่มงานใหม่")
    new_task_title = st.text_input("ชื่อชื่องาน")
    new_task_desc = st.text_area("รายละเอียดงาน")
    if st.button("สร้างงาน"):
        st.warning("ฟังก์ชันสร้างงานต้องเชื่อมต่อ GitHub API POST (ใช้งานได้จริงเมื่อตั้งค่า Write Permission)")
