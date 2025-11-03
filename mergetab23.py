import os
import re
import time
import json
import logging
import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
import jdatetime
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt
from datetime import date

# ----------------------------
# ✅ نرمال‌سازی فارسی
# ----------------------------
def normalize_persian(text: str) -> str:
    if not isinstance(text, str): return text
    mapping = {"ي":"ی","ى":"ی","ئ":"ی","ك":"ک","‌":"", "\u200c":"", "\u200f":"", "‍":""}
    for a,b in mapping.items(): text = text.replace(a,b)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_records(records):
    people = {}
    for r in records:
        name = normalize_persian(r.get("نام",""))
        nid = re.sub(r'\D', '', r.get("کد ملی",""))
        key = nid if len(nid)==10 else name
        if key in people:
            people[key].update(r)
        else:
            r["نام"] = name
            r["کد ملی"] = nid
            people[key] = r
    return list(people.values())

# ----------------------------
# ✅ تاریخ شمسی → میلادی
# ----------------------------
def to_gregorian(d):
    y,m,d = map(int, d.split("/"))
    g = jdatetime.date(y,m,d).togregorian()
    return date(g.year, g.month, g.day)

# ----------------------------
# ✅ نمودار تایم لاین
# ----------------------------
def plot_timeline(df, title):
    plt.figure(figsize=(10,4))
    for i,r in df.iterrows():
        plt.plot([r["start"], r["end"]], [r["نام"], r["نام"]], marker="o")
    plt.title(title)
    plt.xlabel("Timeline")
    plt.ylabel("Persons")
    plt.grid(True)
    st.pyplot(plt)

# ----------------------------
# ✅ پردازش LLM (فعلاً نمایشی)
# ----------------------------
def llm_extract(data):
    import google.generativeai as genai
    from google.genai import types
    # 1️⃣ --- حذف کامل پیام‌های هشدار و لاگ‌های داخلی ---
    os.environ["GRPC_VERBOSITY"] = "NONE"
    os.environ["GLOG_minloglevel"] = "2"
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

    # 2️⃣ --- تنظیم API Key ---
    apikey = "AIzaSyAALSr7TI81SZ6e0X9tLk14GJJk37CkMgQ"

    genai.configure(api_key=apikey)

    # 3️⃣ --- تبدیل کل JSON به رشته (برای جلوگیری از خطای dict) ---
    prompt = json.dumps(data, ensure_ascii=False, indent=2)

    # 4️⃣ --- تعریف دستورالعمل سیستم ---
    system_instruction = """نقش: شما یک تحلیلگر متخصص حقوقی و شرکتی هستید که در زمینه بررسی اسناد رسمی و روزنامه‌های کثیرالانتشار تخصص دارید.
    موضوع: ورودی حاوی تاریخچه آگهی‌های ثبت‌شده در روزنامه رسمی برای یک شرکت است.
    وظیفه اصلی: با تحلیل دقیق و به ترتیب زمانی متن آگهی‌ها، هر عضو این شرکت را شناسایی و با تاریخ شروع و پایان مسئولیت معرفی کنید.

    مراحل اجرا:
    1. ابتدا تمام آگهی‌ها را بر اساس «تاریخ نامه» یا «تاریخ روزنامه» از قدیمی‌ترین به جدیدترین مرتب کنید.
    2. متن هر آگهی را بررسی کنید تا اطلاعات مربوط به اعضای شرکت (مدیرعامل، هیئت‌مدیره، بازرس و...) استخراج شود.
    3. در صورت وجود، تاریخ شروع و پایان مسئولیت را تعیین کنید.
    4. خروجی را دقیقاً در قالب JSON زیر تولید کنید:
    {
    "نام شرکت": "string or null",
    "شناسه شرکت": "number or null",
    "اعضای فعلی شرکت": [
        {"نام": "string or null", "کد ملی": "string or null", "سمت": "string or null", "تاریخ شروع": "string or null", "تاریخ پایان": "string or null", "شماره روزنامه": "string or null"}
    ],
    "اعضای سابق شرکت": [
        {"نام": "string or null", "کد ملی": "string or null", "سمت": "string or null", "تاریخ شروع": "string or null", "تاریخ پایان": "string or null", "شماره روزنامه": "string or null"}
    ]
    }
    """

    # 5️⃣ --- ساخت مدل Gemini ---
    model = genai.GenerativeModel(
        model_name="gemini-2.5-pro",  # تصحیح مدل به نسخه معتبر
        system_instruction=system_instruction
    )

    # 6️⃣ --- تولید خروجی JSON ---
    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2
        }
    )

    # 7️⃣ --- ذخیره نتیجه در فایل خروجی ---
    output_path = "company_members.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    # 8️⃣ --- بازگشت محتوای JSON برای نمایش در Streamlit ---
    with open(output_path, "r", encoding="utf-8") as f:
        return json.load(f)

    result = json.loads(response.text)

    # ✅ نرمال سازی خروجی LLM
    result["اعضای فعلی شرکت"] = normalize_records(result.get("اعضای فعلی شرکت", []))
    result["اعضای سابق شرکت"] = normalize_records(result.get("اعضای سابق شرکت", []))

    return result

# -------------------------------------------
# ✅ UI — only one dashboard screen
# -------------------------------------------
st.set_page_config(page_title="تحلیل روزنامه رسمی", layout="wide")

st.markdown("""
<h2 style='text-align:right; direction:rtl;'>📊 تحلیل هوشمند آگهی‌های روزنامه رسمی و اعضای شرکت</h2>
<p style='text-align:right; direction:rtl;'>فایل JSON آگهی‌ها را آپلود کنید تا سیستم افراد، سمت‌ها و بازه زمانی فعالیت را استخراج و نمایش دهد.</p>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("📂 فایل JSON روزنامه رسمی", type=["json"], label_visibility="visible")

if uploaded:
    ads = json.load(uploaded)

    with st.spinner("⏳ درحال پردازش با هوش مصنوعی..."):
        parsed = llm_extract(ads)

    members_now = normalize_records(parsed.get("اعضای فعلی شرکت", []))
    members_old = normalize_records(parsed.get("اعضای سابق شرکت", []))
    all_members = members_now + members_old

    rows=[]
    for p in all_members:
        try:
            rows.append([
                p["نام"], p["سمت"],
                to_gregorian(p["تاریخ شروع"]),
                to_gregorian(p["تاریخ پایان"]),
                p["شماره روزنامه"]
            ])
        except:
            pass

    df = pd.DataFrame(rows, columns=["نام","سمت","start","end","شماره روزنامه"])

    # جدا سازی نمودار مدیرعامل و هیئت
    df_board = df[df["سمت"].str.contains("مدیرعامل|هیئت مدیره")]
    df_member = df[~df["سمت"].str.contains("مدیرعامل|هیئت مدیره")]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("👥 تعداد اعضا", len(df_member))
    with col2:
        st.metric("🏛 تعداد مدیران و هیئت‌مدیره", len(df_board))

    st.subheader("👤 اعضای شرکت")
    plot_timeline(df_member, "Timeline - اعضای شرکت")

    st.subheader("🏛 مدیرعامل و هیئت‌مدیره")
    plot_timeline(df_board, "Timeline - هیئت‌مدیره و مدیرعامل")

    st.download_button("📥 دانلود خروجی پردازش‌شده", 
        data=json.dumps(all_members, ensure_ascii=False),
        file_name="members_clean.json", mime="application/json")
