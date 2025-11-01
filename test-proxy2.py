import requests

proxy = {
    "http": "http://7h8o8te9k6:LuDCEq3Rv7@85.185.120.203:42073",
    "https": "http://7h8o8te9k6:LuDCEq3Rv7@85.185.120.203:42073"
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
        r = requests.get("https://rrk.ir/", proxies=proxy, timeout=30)
        print(r.status_code)
        print(r.text[:500])
