import requests

# Proxy credentials
proxy_user = "7h8o8te9k6"
proxy_pass = "LuDCEq3Rv7"
proxy_host = "85.185.120.203"
proxy_port = "42073"

proxies = {
    "http": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
    "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
}

# ----------------------------------
# رابط کاربری Streamlit
# ----------------------------------
import streamlit as st
st.title("تست پروکسی روی RRK.ir")

tab1, = st.tabs(["تست پروکسی"])

# --------------------------
# تب 1: استخراج جدید
# --------------------------
with tab1:
    st.markdown("تست proxy")
    start_btn = st.button("شروع تست")

    if start_btn:
        r = requests.get("https://rrk.ir/", proxies=proxies, timeout=30)
        print(r.status_code)
        print(r.text[:500])
