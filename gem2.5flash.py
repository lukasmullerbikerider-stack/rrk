# -*- coding: utf-8 -*-
"""
نسخه فارسی + راست‌به‌چپ + تحلیل هوشمند
بدون هیچ نامی از Gemini در UI
ورودی: چندین شرکت / چندین آگهی مخلوط
"""

import os
import re
import io
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from dateutil import parser as date_parser
import jdatetime

# ==========================
# پیکربندی UI
# ==========================
st.set_page_config(page_title="تحلیل هوشمند روزنامه رسمی", layout="wide")
st.markdown("<div dir='rtl' style='text-align:right;font-family:Tahoma;'>", unsafe_allow_html=True)
st.title("📰 سامانه تحلیل هوشمند آگهی‌های روزنامه رسمی")

# ==========================
# نرمال‌سازی فارسی/عربی
# ==========================
ARABIC_TO_PERSIAN = str.maketrans({
    "ي":"ی","ى":"ی","ك":"ک","ؤ":"و","أ":"ا","إ":"ا","ۀ":"ه","ي":"ی"
})
NUM_AR = str.maketrans({
    "۰":"0","۱":"1","۲":"2","۳":"3","۴":"4","۵":"5","۶":"6","۷":"7","۸":"8","۹":"9"
})

def normalize(s):
    if not s: return s
    s = s.translate(ARABIC_TO_PERSIAN)
    s = s.translate(NUM_AR)
    s = re.sub(r"\s+"," ",s)
    return s.strip()

def normalize_name(s):
    if not s: return s
    s = normalize(s)
    s = re.sub(r"[^\u0600-\u06FF\s\-]", "", s)
    return s.strip()

# ==========================
# استانداردسازی سمت‌ها
# ==========================
ROLE_MAP = {
    "مدیرعامل": ["مدیرعامل","مدیر عامل"],
    "رئیس هیئت مدیره": ["رئیس هیئت","رئیس هیات","رئیس هیئت مدیره"],
    "نایب رئیس هیئت مدیره": ["نایب","نائب","نایب رئیس","نائب رئیس"],
    "عضو هیئت مدیره": ["عضو هیئت","عضو هیات","عضو هیئت مدیره"],
    "بازرس اصلی": ["بازرس اصلی","بازرس"],
    "بازرس علی‌البدل": ["بازرس علی","علی البدل"],
    "مؤسسه حسابرسی": ["موسسه","مؤسسه"]
}

def standardize_role(r):
    r = normalize(r or "")
    for std, lst in ROLE_MAP.items():
        for x in lst:
            if x in r:
                return std
    return r

# ==========================
# تبدیل تاریخ شمسی → میلادی
# ==========================
def to_gregorian(d):
    if not d: return None
    d = normalize(d)
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", d)
    if m:
        y,mo,da = map(int, m.groups())
        if y>1300:
            try: return jdatetime.date(y,mo,da).togregorian()
            except: pass
    try: return date_parser.parse(d)
    except: return None

# ==========================
# تحلیل هوشمند (پشت صحنه هوش مصنوعی)
# ==========================

def smart_extract_members_from_ad(text, meta):
    """
    نسخه ساده‌شده برای استخراج هوشمند
    در نسخه نهایی شما اینجا فراخوانی مدل هوش مصنوعی قرار خواهد گرفت.
    ولی UI هیچ اشاره‌ای به مدل ندارد.
    """
    text = normalize(text)
    members = []

    # الگوی تشخیص فرد: «آقای / خانم / نام + کد ملی + سمت»
    person_re = re.finditer(
        r"(آقای|خانم)\s+([آ-ی\s]{2,40})(?:\s*به شماره ملی\s*(\d{10}))?\s*(?:به سمت\s*([^،\.\n]+))?",
        text
    )

    for m in person_re:
        name = normalize_name(m.group(2))
        nid = m.group(3)
        role_raw = normalize(m.group(4) or "")
        role_std = standardize_role(role_raw)
        members.append({
            "name": name,
            "national_id": nid,
            "role_raw": role_raw,
            "role_standard": role_std,
            "start_date_jalali": meta.get("start"),
            "end_date_jalali": None,
            "newspaper_no": meta.get("news")
        })

    return {
        "company_name": meta.get("company"),
        "company_national_id": meta.get("company_id"),
        "members": members
    }

# ==========================
# پردازش کل فایل
# ==========================

def process_ads(ads):
    all_members = []

    for ad in ads:
        text = ad.get("متن آگهی") or ad.get("text") or ""
        company = normalize(ad.get("نام شرکت"))
        company_id = normalize(ad.get("شناسه ملی شرکت"))
        news_no = normalize(ad.get("شماره روزنامه"))
        start_date = normalize(ad.get("تاریخ روزنامه") or ad.get("تاریخ نامه"))

        meta = {
            "company": company,
            "company_id": company_id,
            "news": news_no,
            "start": start_date
        }

        result = smart_extract_members_from_ad(text, meta)

        for m in result["members"]:
            sd = to_gregorian(m["start_date_jalali"])
            ed = to_gregorian(m["end_date_jalali"])

            all_members.append({
                "company_name": result["company_name"],
                "company_national_id": result["company_national_id"],
                "name": m["name"],
                "national_id": m["national_id"],
                "role_raw": m["role_raw"],
                "role_standard": m["role_standard"],
                "start_date_jalali": m["start_date_jalali"],
                "end_date_jalali": m["end_date_jalali"],
                "start_date": sd,
                "end_date": ed,
                "newspaper_no": m["newspaper_no"]
            })

    return pd.DataFrame(all_members)

# ==========================
# نمودارها
# ==========================

def timeline(df, title):
    if df.empty:
        st.warning("داده‌ای برای نمودار موجود نیست.")
        return

    fig = go.Figure()

    for _, r in df.iterrows():
        label = f"{r['name']} - {r['role_standard']}"
        start = r["start_date"] or datetime.now()
        end = r["end_date"] or datetime.now()

        fig.add_trace(go.Scatter(
            x=[start, end],
            y=[label, label],
            mode="lines+markers",
            line=dict(width=8),
            marker=dict(size=6)
        ))

    fig.update_layout(title=title, template="plotly_white", height=450)
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

# ==========================
# UI — بارگذاری فایل
# ==========================

st.subheader("📥 بارگذاری فایل آگهی‌ها (JSON)")

file = st.file_uploader("فایل را انتخاب کنید", type=["json"])

if file:
    ads = json.load(file)
    st.success(f"✔ تعداد {len(ads)} آگهی بارگذاری شد")

    if st.button("🔍 شروع تحلیل هوشمند"):
        with st.spinner("در حال تحلیل هوشمند آگهی‌ها..."):
            df = process_ads(ads)

        st.success("🎯 تحلیل کامل شد")
        st.dataframe(df)

        # دانلود JSON
        st.download_button(
            "📥 دانلود JSON خروجی",
            data=df.to_json(orient="records", force_ascii=False),
            file_name="members.json"
        )

        # دانلود Excel
        output = io.BytesIO()
        df.to_excel(output, index=False)
        st.download_button(
            "📊 دانلود Excel",
            data=output,
            file_name="members.xlsx"
        )

        st.markdown("## 📊 نمودارها")

        # ۱- اعضای مهم فعلی
        key_roles = ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره"]
        df_key = df[df["role_standard"].isin(key_roles)]
        timeline(df_key, "تایم‌لاین اعضای کلیدی شرکت")

        # ۲- همه اعضا
        timeline(df, "تایم‌لاین همه اعضا از ابتدای حضور")

        # ۳- دسته‌بندی نقش‌ها
        st.markdown("### ⏳ تایم‌لاین دسته‌بندی سمت‌ها")

        for role in df["role_standard"].unique():
            timeline(df[df["role_standard"] == role], f"سمت: {role}")

st.markdown("</div>", unsafe_allow_html=True)
