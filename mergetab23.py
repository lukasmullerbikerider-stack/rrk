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
import plotly.express as px

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


def charts(data):
    import pandas as pd
    import plotly.express as px
    import streamlit as st

    # ✅ 1. آماده‌سازی داده‌ها
    current = data.get("اعضای فعلی شرکت", [])
    past = data.get("اعضای سابق شرکت", [])

    all_members = []
    for m in current:
        m["وضعیت"] = "فعلی"
        all_members.append(m)
    for m in past:
        m["وضعیت"] = "سابق"
        all_members.append(m)

    df = pd.DataFrame(all_members)

    # اگر ستونی خالی بود (به دلیل نبود داده)، جایگزین مقدار خالی شود
    df = df.fillna("نامشخص")

    # 🌈 CSS سفارشی برای استایل کارت‌ها
    st.markdown("""
    <style>
    .card {
        background-color: rgba(250, 250, 250, 0.9);
        border-radius: 20px;
        padding: 25px;
        margin-bottom: 30px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    .card:hover {
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        transform: translateY(-3px);
    }
    .card h3 {
        color: #2E3A59;
        margin-bottom: 10px;
    }
    .card p {
        color: #555;
        font-size: 0.9rem;
        margin-top: -8px;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## 📊 داشبورد تحلیلی اعضا و مدیران شرکت")
    st.info("در این بخش سه نمودار تفکیک‌شده برای اعضا، مدیران و مقایسه کلی نمایش داده می‌شود.")

    # ------------------------------------------------------------------
    # 🟦 کارت اول: اعضای شرکت
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👥 اعضای شرکت")
        st.markdown("<p>این نمودار تعداد اعضای شرکت را در طول زمان نمایش می‌دهد.</p>", unsafe_allow_html=True)

        colA1, colA2 = st.columns(2)
        with colA1:
            date_col1 = st.selectbox("📅 ستون تاریخ اعضا:", df.columns, index=list(df.columns).index("تاریخ شروع"))
        with colA2:
            name_col1 = st.selectbox("📛 ستون نام افراد:", df.columns, index=list(df.columns).index("نام"))

        df_members = df.groupby(df[date_col1])[name_col1].count().reset_index()
        df_members.columns = ["date", "count"]

        fig_members = px.line(
            df_members, x="date", y="count", markers=True,
            title="📈 روند تغییرات اعضای شرکت"
        )
        fig_members.update_layout(
            xaxis_title="تاریخ",
            yaxis_title="تعداد اعضا",
            plot_bgcolor="rgba(0,0,0,0)"
        )

        st.plotly_chart(fig_members, use_container_width=True)
        st.download_button(
            "📥 دانلود داده اعضا (CSV)",
            df_members.to_csv(index=False).encode("utf-8"),
            "members_chart_data.csv",
            "text/csv"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 🟨 کارت دوم: مدیرعامل و هیئت مدیره
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👔 مدیرعامل و هیئت مدیره")
        st.markdown("<p>نمودار تغییرات مدیرعامل و اعضای هیئت مدیره در طول زمان.</p>", unsafe_allow_html=True)

        colB1, colB2, colB3 = st.columns(3)
        with colB1:
            date_col2 = st.selectbox("📅 ستون تاریخ:", df.columns, index=list(df.columns).index("تاریخ شروع"))
        with colB2:
            role_col = st.selectbox("🎭 ستون سمت/نقش:", df.columns, index=list(df.columns).index("سمت"))
        with colB3:
            roles_selected = st.multiselect(
                "🔎 نقش‌هایی که نمایش داده شود:",
                sorted(df[role_col].unique()),
                default=sorted(df[role_col].unique())
            )

        df_role = df[df[role_col].isin(roles_selected)]
        df_role_count = (
            df_role.groupby([df_role[date_col2], df_role[role_col]])
            .size()
            .reset_index(name="count")
        )
        df_role_count.columns = ["date", "role", "count"]

        fig_roles = px.line(
            df_role_count, x="date", y="count", color="role", markers=True,
            title="📉 روند تغییرات مدیرعامل و هیئت مدیره"
        )
        fig_roles.update_layout(
            xaxis_title="تاریخ",
            yaxis_title="تعداد",
            legend_title_text="سمت",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_roles, use_container_width=True)

        st.download_button(
            "📥 دانلود داده مدیران (CSV)",
            df_role_count.to_csv(index=False).encode("utf-8"),
            "board_chart_data.csv",
            "text/csv"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 🟩 کارت سوم: نمودار ترکیبی
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🔄 نمودار ترکیبی اعضا و مدیران")
        st.markdown("<p>نمودار مقایسه‌ای میان روند تغییرات اعضا و مدیران شرکت.</p>", unsafe_allow_html=True)

        try:
            df_combined = pd.concat([
                df_members.assign(type="اعضا"),
                df_role_count.groupby("date")["count"].sum().reset_index().assign(type="مدیران")
            ])

            fig_combined = px.line(
                df_combined, x="date", y="count", color="type", markers=True,
                title="📊 مقایسه اعضا و مدیران"
            )
            fig_combined.update_layout(
                xaxis_title="تاریخ",
                yaxis_title="تعداد افراد",
                legend_title_text="دسته‌بندی",
                plot_bgcolor="rgba(0,0,0,0)"
            )

            st.plotly_chart(fig_combined, use_container_width=True)
            st.download_button(
                "📥 دانلود داده ترکیبی (CSV)",
                df_combined.to_csv(index=False).encode("utf-8"),
                "combined_chart_data.csv",
                "text/csv"
            )
        except Exception as e:
            st.warning(f"⚠️ داده کافی برای رسم نمودار ترکیبی وجود ندارد: {e}")

        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------
# ✅ UI — only one dashboard screen
# -------------------------------------------
st.set_page_config(page_title="تحلیل روزنامه رسمی", layout="wide")

st.markdown("""
<h2 style='text-align:right; direction:rtl;'>📊 تحلیل هوشمند آگهی‌های روزنامه رسمی و اعضای شرکت</h2>
<p style='text-align:right; direction:rtl;'>فایل JSON آگهی‌ها را آپلود کنید تا سیستم افراد، سمت‌ها و بازه زمانی فعالیت را استخراج و نمایش دهد.</p>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("📂 فایل JSON روزنامه رسمی", type=["json"], label_visibility="visible")
uploaded2 = st.file_uploader("📂 فایل اعضای شرکت", type=["json"], label_visibility="visible")

if uploaded:
    ads = json.load(uploaded)

    with st.spinner("⏳ درحال پردازش با هوش مصنوعی..."):
        parsed = llm_extract(ads)

if uploaded2:
    membersdata =  json.load(uploaded2)
    charts(membersdata)


    st.download_button("📥 دانلود خروجی پردازش‌شده", 
        data=json.dumps(all_members, ensure_ascii=False),
        file_name="members_clean.json", mime="application/json")
