# dashboard.py
import streamlit as st
import psutil
import time
from datetime import datetime

st.set_page_config(page_title="Synergesis Monitor", layout="wide")
st.title("🧠 Synergesis Agent System Monitor")

# Refresh every 5 seconds
st_autorefresh = st.empty()

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🖥️ System")
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory()
    st.metric("CPU Usage", f"{cpu}%")
    st.metric("RAM Usage", f"{mem.percent}%")
    st.progress(mem.percent / 100)

with col2:
    st.subheader("💾 Memory & Disk")
    disk = psutil.disk_usage("/")
    st.metric("Disk Used", f"{disk.percent}%")
    st.progress(disk.percent / 100)
    st.write(f"Available: {disk.free // (2**30)} GB")

with col3:
    st.subheader("🧩 Agent Status")
    try:
        with open("synergesis.log", "r") as f:
            lines = f.readlines()[-5:]
        st.text_area("Recent Logs", "".join(lines), height=200)
    except:
        st.text("No logs yet")

# Auto-refresh
if "run" not in st.session_state:
    st.session_state.run = True

if st_autorefresh:
    time.sleep(5)
    st.rerun()
