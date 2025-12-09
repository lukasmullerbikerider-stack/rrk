# -*- coding: utf-8 -*-
"""
rrk_gemini_streamlit.py
Streamlit app:
- خواندن JSON آگهی‌ها
- ایجاد پرامپت برای Gemini 2.5 Flash برای هر آگهی
- نرمال‌سازی فارسی/عربی و استانداردسازی سمت‌ها
- ذخیره خروجی JSON و Excel
- رسم 3 نمودار تایم‌لاین پیوسته
"""

import os
import re
import io
import json
from datetime import datetime
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import jdatetime
from dateutil import parser as date_parser

# try to import Google GenAI client
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

st.set_page_config(page_title="RRK → Gemini استخراج اعضا", layout="wide")
st.title("🔎 استخراج اعضای شرکت از آگهی‌های روزنامه رسمی — Gemini 2.5 Flash")

# ---------------------------
# کمک‌تابع‌های نرمال‌سازی (فارسی/عربی)
# ---------------------------
ARABIC_TO_PERSIAN = str.maketrans({
    "ك":"ک", "ي":"ی", "ى":"ی", "إ":"ا", "أ":"ا", "ٱ":"ا",
    " ":" ", "\u200c":"", "\u200f":"", "\u200e":""
})
AR_NUM_TO_EN = str.maketrans({
    "۰":"0","۱":"1","۲":"2","۳":"3","۴":"4","۵":"5","۶":"6","۷":"7","۸":"8","۹":"9",
    "٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9"
})

def normalize_text(s: str) -> str:
    """نرمال‌سازی: تبدیل حروف عربی→فارسی، اعداد عربی→انگلیسی، حذف کاراکترهای نامرئی"""
    if not s:
        return s
    s = s.strip()
    s = s.translate(ARABIC_TO_PERSIAN)
    s = s.translate(AR_NUM_TO_EN)
    # فشرده‌سازی فاصله‌ها و حذف کاراکترهای اضافی
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_name(name: str) -> str:
    if not name: return name
    name = normalize_text(name)
    name = re.sub(r"[^\w\s\u0600-\u06FF\-ٔٔ‌]", "", name)  # نگه داشتن حروف فارسی/عربی/فاصله/خط تیره
    return name.strip()

def extract_national_id(text: str) -> str:
    # کدملی ایرانی معمولا 10 رقمی؛ بعضا با صفر پیشرو. جستجوی توالی 10 رقم
    if not text: return None
    m = re.search(r"\b(\d{10})\b", text)
    return m.group(1) if m else None

# ---------------------------
# تبدیل تاریخ شمسی (YYYY/MM/DD یا YYYY-MM-DD) به datetime میلادی
# و fallback پارس میلادی
# ---------------------------
def shamsi_to_gregorian_safe(date_str: str):
    if not date_str or not str(date_str).strip():
        return None
    s = normalize_text(str(date_str))
    # احتمال فرمت شمسی: سال >= 1300 و فرمت با "/"
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m:
        y, mo, d = map(int, (m.group(1), m.group(2), m.group(3)))
        if y >= 1300:  # فرض شمسی
            try:
                return jdatetime.date(y, mo, d).togregorian()
            except Exception:
                pass
    # fallback: اگر میلادی قابل پارس کردن باشد
    try:
        return date_parser.parse(s, dayfirst=True)
    except Exception:
        return None

# ---------------------------
# نقش: استانداردسازی سمت‌ها
# یک دیکشنری از انواع حالت‌های نوشتاری به شکل استاندارد
# ---------------------------
ROLE_MAP = {
    # رئیس
    "رئیس هیئت مدیره": ["رئیس هیئت مدیره", "رئیس و عضو هیئت مدیره", "رئیس هیئت‌مدیره", "رئیس هیئت"],
    # نایب/نائب
    "نایب رئیس هیئت مدیره": ["نایب رئیس", "نائب رئیس", "نایب رییس", "نائب رییس", "نایب"],
    # مدیرعامل
    "مدیرعامل": ["مدیرعامل", "مدیر عامل", "مدیر عامل (خارج از اعضاء)", "مدیرعامل (خارج از اعضاء)"],
    # عضو هیئت مدیره
    "عضو هیئت مدیره": ["عضو هیئت مدیره", "اعضای هیئت مدیره", "عضو و رئیس هیئت مدیره", "عضو و نایب رئیس هیئت مدیره", "عضو اصلی هیئت مدیره"],
    # بازرس
    "بازرس اصلی": ["بازرس اصلی", "بازرس"],
    "بازرس علی‌البدل": ["بازرس علی البدل", "بازرس علی‌البدل", "بازرس علی البدل"]
}

def standardize_role(raw_role: str) -> str:
    if not raw_role:
        return None
    r = normalize_text(raw_role)
    for std, variants in ROLE_MAP.items():
        for v in variants:
            if v in r:
                return std
    # fallback heuristics
    if "مدیر" in r:
        return "مدیرعامل"
    if "رئیس" in r:
        return "رئیس هیئت مدیره"
    if "نایب" in r or "نائب" in r:
        return "نایب رئیس هیئت مدیره"
    if "بازرس" in r:
        # مشخص‌سازی علی‌البدل اگر کلمه البدل موجود باشد
        if "بدل" in r or "علی" in r:
            return "بازرس علی‌البدل"
        return "بازرس اصلی"
    if "عضو" in r:
        return "عضو هیئت مدیره"
    return r  # اگر نشناسیم، همان رشته نرمال‌شده را برگردان

# ---------------------------
# ساخت پرامپت برای Gemini (یک پرامپت نمونه)
# - ما از فرمت JSON انتظار می‌کشیم
# ---------------------------
PROMPT_SYSTEM = """
شما یک استخراج‌گر اطلاعات سازمانی هستید. هر ورودی متن آگهی روزنامه رسمی را دریافت می‌کنید.
وظیفه: از متن آگهی اطلاعات افراد / اشخاص حقوقی معرفی‌شده استخراج کن.
برای هر نفر باید آیتم‌های زیر را دقیق برگردانید:
- نام (فارسی یا عربی) (field: name)
- national_id (کد ملی اگر وجود دارد، به صورت رشته، یا null)
- role_raw (عبارت دقیق سمت در متن آگهی)
- role_standard (یک از: 'مدیرعامل', 'رئیس هیئت مدیره', 'نایب رئیس هیئت مدیره', 'عضو هیئت مدیره', 'بازرس اصلی', 'بازرس علی‌البدل', 'موسسه حسابرسی' یا بهترین گزینهٔ معادل)
- start_date (تاریخ شروع در همان فرمت آگهی، ترجیحا شمسی yyyy/mm/dd یا null)
- end_date (تاریخ پایان اگر وجود دارد، یا null)
- newspaper_no (شماره روزنامه از رکورد ورودی یا null)

فرمت خروجی باید یک JSON باشد به شکل:
{
  "company_name": "...",
  "company_national_id": "...",
  "ad_reference": "...",    // شماره نامه یا شماره پیگیری
  "members": [
    {"name":"...", "national_id":"...", "role_raw":"...", "role_standard":"...", "start_date":"...", "end_date":"...", "newspaper_no":"..."},
    ...
  ]
}
"""

PROMPT_INSTRUCTION = """
ورودی: متن آگهی (متغیر: AD_TEXT) و فیلدهای متنی دیگر (تاریخ روزنامه، شماره روزنامه، شماره پیگیری).
لطفا با دقت تمام افراد (اشخاص حقیقی و حقوقی) را استخراج کن و جاهایی که نام/کدملی/تاریخ وجود ندارد مقدار null قرار بده.
اگر اطلاعات ناقص است، با بهترین گمان منطقی پر کنید ولی حدس‌های ناپایدار را null بگذارید.
خروجی باید valid JSON باشد و هیچ متن اضافه‌ای چاپ نکند.
"""

# ---------------------------
# تابع فراخوانی Gemini
# ---------------------------
def call_gemini_for_ad(ad: Dict[str,Any], model_name="gemini-2.5-flash", api_key_env="GOOGLE_API_KEY", timeout_s=30):
    """
    - ad: یک دیکشنری آگهی با کلیدهای متن آگهی، تاریخ روزنامه، شماره روزنامه و شماره پیگیری
    - برمی‌گرداند: دیکشنری JSON تحلیل‌شده یا raises روی خطا
    """
    # normalize input
    ad_text = normalize_text(ad.get("متن آگهی","") or ad.get("text","") or "")
    newspaper = normalize_text(ad.get("شماره روزنامه","") or ad.get("newspaper","") or "")
    ref = ad.get("شماره پیگیری") or ad.get("شماره نامه") or ad.get("ref") or None

    # اگر genai نصب شده و کلید API وجود دارد، فراخوانی کن
    if GENAI_AVAILABLE and os.environ.get(api_key_env):
        genai.configure(api_key=os.environ.get(api_key_env))
        prompt = PROMPT_SYSTEM + PROMPT_INSTRUCTION + "\n\nAD_TEXT:\n" + ad_text + f"\n\nNEWSPAPER: {newspaper}\nREF: {ref}\n"
        try:
            # استفاده از متد generate برای متون بزرگ
            response = genai.generate(
                model=model_name,
                prompt=prompt,
                max_output_tokens=1024
            )
            # response.text ممکن است رشته JSON باشد
            text = response.text if hasattr(response, "text") else str(response)
            # تلاش برای بارگذاری JSON محتوایی
            out = json.loads(text)
            return out
        except Exception as e:
            st.warning(f"خطا در فراخوانی Gemini: {e} — از fallback محلی استفاده می‌شود.")
            return heuristic_ad_parser(ad)
    else:
        # fallback: تحلیل heuristics محلی (regex-based)
        return heuristic_ad_parser(ad)

# ---------------------------
# تحلیلگر محلی fallback (قابل توسعه)
# ---------------------------
def heuristic_ad_parser(ad: Dict[str,Any]) -> Dict[str,Any]:
    """
    تحلیل سادهٔ محلی: استخراج اسامی، کدملی و سمت‌ها از متن آگهی با regex و قواعد ساده.
    هدف: زمانی که Gemini در دسترس نیست، خروجی معقول تولید شود.
    """
    text = normalize_text(ad.get("متن آگهی","") or "")
    newspaper = normalize_text(ad.get("شماره روزنامه","") or "")
    ref = ad.get("شماره پیگیری") or ad.get("شماره نامه")
    members = []
    # جداسازی بندها بر اساس عبارات متداول "آقای" و "خانم" و یا "شرکت"
    parts = re.split(r"(?:آقای|خانم|شرکت|مؤسسه|موسسه|شرکت\s+)", text)
    # اما نگه داشتن علائم بهتر: از finditer برای الگوهای کاملتر استفاده می‌کنیم
    # الگوی ساده برای "نام ... به شماره ملی ... به سمت ... تا تاریخ ..."
    person_pattern = re.compile(
        r"(?P<name>[آ-ی\s\-]{2,60})\s*(?:به شماره ملی\s*(?P<nid>\d{10}))?\s*(?:به سمت|بسمت|بسمت)\s*(?P<role>[^،\.\n]+?)\s*(?:تا تاریخ\s*(?P<end>\d{2,4}[\/\-]\d{1,2}[\/\-]\d{1,2}))?",
        flags=re.IGNORECASE
    )
    # همچنین جستجوی الگوهای 'مؤسسه' یا 'موسسه' به عنوان بازرس
    org_pattern = re.compile(r"(موسسه|مؤسسه|شرکت)\s+([آ-ی0-9\s\-\u0600-\u06FF]+)")
    # جستجوی با person_pattern
    for m in person_pattern.finditer(text):
        name = normalize_name(m.group("name")) if m.group("name") else None
        nid = m.group("nid") if m.group("nid") else extract_national_id(m.group(0))
        role_raw = m.group("role").strip() if m.group("role") else None
        role_standard = standardize_role(role_raw)
        end = m.group("end") if m.group("end") else None
        members.append({
            "name": name,
            "national_id": nid,
            "role_raw": role_raw,
            "role_standard": role_standard,
            "start_date": ad.get("تاریخ نامه") or ad.get("تاریخ روزنامه"),
            "end_date": end,
            "newspaper_no": newspaper
        })
    # در صورتی که الگویی پیدا نشد، یک جستجوی کلی برای 'بازرس' و موسسات
    if not members:
        # موسسات
        for m in org_pattern.finditer(text):
            org = normalize_text(m.group(0))
            members.append({
                "name": org,
                "national_id": None,
                "role_raw": "موسسه حسابرسی",
                "role_standard": "موسسه حسابرسی",
                "start_date": ad.get("تاریخ نامه") or ad.get("تاریخ روزنامه"),
                "end_date": None,
                "newspaper_no": newspaper
            })
    result = {
        "company_name": normalize_text(ad.get("نام شرکت") or ""),
        "company_national_id": ad.get("شناسه ملی شرکت") or None,
        "ad_reference": ref,
        "members": members
    }
    return result

# ---------------------------
# پس‌پردازش جمعی: ساخت DataFrame واحد از همه آگهی‌ها
# ---------------------------
def process_ads_with_gemini(ads: List[Dict[str,Any]], call_gemini_fn) -> Dict[str,Any]:
    """
    - ads: لیست آگهی‌ها
    - call_gemini_fn: تابعی که یک آگهی را می‌گیرد و JSON خروجی را برمی‌گرداند
    خروجی: دیکشنری کلی شامل اعضای ترکیبی (اعضای فعلی/سابق با نرمال‌سازی)
    """
    all_members = []  # لیست رکوردها
    errors = []
    for idx, ad in enumerate(ads):
        try:
            out = call_gemini_fn(ad)
            comp = out.get("company_name") or ad.get("نام شرکت")
            comp_id = out.get("company_national_id") or ad.get("شناسه ملی شرکت")
            for m in out.get("members", []):
                # نرمال‌سازی نام و role
                name = normalize_name(m.get("name") or "")
                nid = m.get("national_id") or extract_national_id(m.get("name") or "") or None
                role_raw = m.get("role_raw") or ""
                role_std = standardize_role(m.get("role_standard") or role_raw)
                start = m.get("start_date") or ad.get("تاریخ نامه") or ad.get("تاریخ روزنامه")
                end = m.get("end_date") or None
                # تاریخ های میلادی برای رسم
                start_dt = shamsi_to_gregorian_safe(start) if start else None
                end_dt = shamsi_to_gregorian_safe(end) if end else None
                all_members.append({
                    "company_name": comp,
                    "company_national_id": comp_id,
                    "ad_reference": out.get("ad_reference"),
                    "name": name,
                    "national_id": nid,
                    "role_raw": normalize_text(role_raw),
                    "role_standard": role_std,
                    "start_date_jalali": start,
                    "end_date_jalali": end,
                    "start_date": start_dt,
                    "end_date": end_dt,
                    "newspaper_no": m.get("newspaper_no") or ad.get("شماره روزنامه")
                })
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})
    return {"members": all_members, "errors": errors}

# ---------------------------
# رسم نمودارهای تایم‌لاین با Plotly
# سه نمودار: اعضای مهم فعلی / همه اعضا / دسته‌بندی سمت‌ها (تاریخ محور)
# ---------------------------
def plot_timelines(df_members: pd.DataFrame):
    # df_members must include columns: name, role_standard, start_date, end_date
    # Fallback: fill missing end_date with today for visualization
    df = df_members.copy()
    if df.empty:
        st.warning("هیچ عضوی برای رسم یافت نشد.")
        return

    df['start_plot'] = df['start_date'].fillna(pd.Timestamp(datetime.now()))
    df['end_plot'] = df['end_date'].fillna(pd.Timestamp(datetime.now()))

    # 1) اعضای مهم فعلی: فیلتر برای role_standard در لیست کلیدی و end_date == NaN یا>today
    key_roles = ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره"]
    today = pd.Timestamp(datetime.now())
    df_current = df[(df['role_standard'].isin(key_roles)) & ((df['end_date'].isna()) | (df['end_date'] >= today))]

    def make_timeline_figure(subdf, title):
        fig = go.Figure()
        # y labels: unique name — role
        subdf = subdf.sort_values(by='start_plot')
        for _, r in subdf.iterrows():
            label = f"{r['name']} — {r['role_standard']}"
            fig.add_trace(go.Scatter(
                x=[r['start_plot'], r['end_plot']],
                y=[label, label],
                mode='lines+markers',
                line=dict(width=8),
                marker=dict(size=6),
                hovertemplate=f"<b>{r['name']}</b><br>{r['role_standard']}<br>شروع: {r['start_date_jalali']}<br>پایان: {r['end_date_jalali'] or '—'}<extra></extra>"
            ))
        fig.update_layout(title=title, template='plotly_white', height=400)
        fig.update_yaxes(autorange="reversed")
        return fig

    fig1 = make_timeline_figure(df_current, "تایم‌لاین — اعضای مهم فعلی")
    st.plotly_chart(fig1, use_container_width=True)

    # 2) همه اعضا از ابتدای زمانی که آمده‌اند (تمام رکوردها)
    fig2 = make_timeline_figure(df, "تایم‌لاین — همه اعضا (تمام تاریخ‌ها)")
    st.plotly_chart(fig2, use_container_width=True)

    # 3) تایم‌لاین دسته‌بندی سمت‌ها: برای هر role_standard، نمایش کانال زمانی تجمعی
    roles = df['role_standard'].fillna('نامشخص').unique().tolist()
    fig3 = go.Figure()
    for role in roles:
        subset = df[df['role_standard']==role]
        # برای رسم، از min(start) تا max(end)
        if subset.empty:
            continue
        min_start = subset['start_plot'].min()
        max_end = subset['end_plot'].max()
        fig3.add_trace(go.Bar(x=[(max_end - min_start).days], y=[role], orientation='h', 
                              base=min_start, name=role, text=[len(subset)], textposition='inside'))
    fig3.update_layout(title="فشرده زمانی سمت‌ها (بازه کلی پوشش)", template='plotly_white', height=400)
    st.plotly_chart(fig3, use_container_width=True)

# ---------------------------
# رابط کاربری Streamlit
# ---------------------------
st.markdown("## ۱) تنظیمات اتصال Gemini (اختیاری)")
col1, col2 = st.columns([2,1])
with col1:
    api_key_input = st.text_input("کلید API Google (اگر می‌خواهید از Gemini استفاده کنید) — می‌توانید ابتدا محیطی ست کنید:", type="password")
    model_name = st.text_input("نام مدل Gemini", value="gemini-2.5-flash")
with col2:
    save_api_env = st.button("ذخیره به متغیر محیطی")
    if save_api_env and api_key_input:
        os.environ["GOOGLE_API_KEY"] = api_key_input
        st.success("کلید API در متغیر محیطی تنظیم شد (فعلاً برای همین پراسس محلی).")

st.markdown("---")
st.markdown("## ۲) بارگذاری فایل JSON آگهی‌ها (یک آرایه از آگهی‌ها)")
uploaded = st.file_uploader("آپلود JSON آگهی‌ها (خروجی scraper یا فایل مشابه)", type=["json"])
if uploaded:
    ads = json.load(uploaded)
    st.success(f"{len(ads)} آگهی بارگذاری شد.")
    if st.checkbox("نمایش جدولی از آگهی‌ها (پیش‌نمایش)"):
        st.dataframe(pd.DataFrame(ads).head(200))

    process_btn = st.button("▶️ پردازش تمام آگهی‌ها با Gemini / fallback")
    if process_btn:
        with st.spinner("در حال پردازش آگهی‌ها — هر آگهی جداگانه پردازش می‌شود..."):
            results = process_ads_with_gemini(ads, lambda ad: call_gemini_for_ad(ad, model_name=model_name))
            members = results["members"]
            errors = results["errors"]
            st.success(f"پردازش کامل شد — {len(members)} رکورد استخراجی — خطاها: {len(errors)}")
            df_members = pd.DataFrame(members)
            # نمایش و دانلود خروجی
            st.subheader("نتایج استخراج شده (نمونه)")
            st.dataframe(df_members.head(200))

            # ذخیره JSON و Excel برای دانلود
            out_json = json.dumps({"members": members}, ensure_ascii=False, indent=2)
            st.download_button("📥 دانلود JSON استخراج‌شده", data=out_json, file_name="extracted_members.json", mime="application/json")

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
                df_members.to_excel(writer, index=False, sheet_name="members")
            towrite.seek(0)
            st.download_button("📊 دانلود Excel (xlsx)", data=towrite, file_name="extracted_members.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # رسم نمودارها
            st.subheader("نمودارهای تایم‌لاین")
            plot_timelines(df_members)
