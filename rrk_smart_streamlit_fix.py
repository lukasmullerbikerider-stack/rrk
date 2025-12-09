# -*- coding: utf-8 -*-
"""
نسخه اصلاح‌شده:
- RTL کامل
- نمایش تاریخ‌ها به شمسی
- نقش‌ها (ROLE_MAP) گسترش یافته
- دو نمودار جدا (Key timeline, All timeline) با امکان دانلود PNG مجزا
- خروجی JSON و Excel
"""

import io, re, json
from datetime import datetime
from typing import Optional
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import jdatetime
from dateutil import parser as date_parser

st.set_page_config(page_title="تحلیل هوشمند آگهی‌ها (اصلاح‌شده)", layout="wide")
# CSS RTL + فونت
st.markdown("""
<style>
body { direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }
.stButton>button { background-color:#2e89ff; color:white; border-radius:6px; padding:8px 16px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div dir='rtl'>", unsafe_allow_html=True)
st.title("🔎 تحلیل هوشمند آگهی‌های روزنامه رسمی — (نسخه اصلاح‌شده)")

# -------------------------
# کمک‌توابع نرمال‌سازی
# -------------------------
AR2FA = str.maketrans({"ك":"ک","ي":"ی","ى":"ی","أ":"ا","إ":"ا","ؤ":"و","ﺀ":"ء","ۀ":"ه"})
NUM2EN = str.maketrans({"۰":"0","۱":"1","۲":"2","۳":"3","۴":"4","۵":"5","۶":"6","۷":"7","۸":"8","۹":"9",
                       "٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9"})

def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = str(s)
    s = s.strip()
    s = s.translate(AR2FA)
    s = s.translate(NUM2EN)
    s = re.sub(r"[\u200c\u200e\u200f]", "", s)  # حذف کاراکترهای نامرئی
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_name(s: Optional[str]) -> str:
    if not s:
        return ""
    s = normalize_text(s)
    s = re.sub(r"[^آ-یA-Za-z\s\-]", "", s)
    return s.strip()

def extract_national_id(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"\b(\d{10})\b", text)
    return m.group(1) if m else None

# -------------------------
# تاریخ — تبدیل و نمایش شمسی
# -------------------------
def shamsi_to_gregorian_safe(date_str: Optional[str]):
    if not date_str:
        return None
    s = normalize_text(date_str)
    # شکل yyyy/mm/dd (شمسی)
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m:
        y,mo,da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y >= 1300:
            try:
                return jdatetime.date(y,mo,da).togregorian()
            except Exception:
                pass
    # fallback parse میلادی
    try:
        return date_parser.parse(s, dayfirst=True)
    except Exception:
        return None

def gregorian_to_jalali_str(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = shamsi_to_gregorian_safe(dt) or date_parser.parse(dt)
    try:
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"
    except Exception:
        return None

# -------------------------
# نقش‌ها — دیکشنری گسترده‌تر
# -------------------------
ROLE_MAP = {
    "مدیرعامل": ["مدیرعامل","مدیر عامل","مدیر عامل (خارج از اعضاء)","مدیرعامل (خارج از اعضاء)"],
    "رئیس هیئت مدیره": ["رئیس هیئت مدیره","رئیس هیئت‌مدیره","رئیس هیئت","رئیس هیات","رئیس و عضو هیئت مدیره"],
    "نایب رئیس هیئت مدیره": ["نایب رئیس هیئت مدیره","نائب رئیس","نایب رئیس","نایب","نائب"],
    "عضو هیئت مدیره": ["عضو هیئت مدیره","اعضای هیئت مدیره","عضو هیئت","عضو هیات","عضو اصلی هیئت مدیره"],
    "بازرس اصلی": ["بازرس اصلی","بازرس"],
    "بازرس علی‌البدل": ["بازرس علی البدل","بازرس علی‌البدل","علی البدل"],
    "موسسه حسابرسی": ["موسسه حسابرسی","مؤسسه حسابرسی","موسسه","مؤسسه"]
}

def standardize_role(raw: Optional[str]) -> str:
    r = normalize_text(raw or "")
    for std, variants in ROLE_MAP.items():
        for v in variants:
            if v in r:
                return std
    # heuristics
    if "مدیر" in r:
        return "مدیرعامل"
    if "رئیس" in r:
        return "رئیس هیئت مدیره"
    if "نائب" in r or "نایب" in r:
        return "نایب رئیس هیئت مدیره"
    if "بازرس" in r:
        return "بازرس اصلی"
    if "موسسه" in r or "مؤسسه" in r:
        return "موسسه حسابرسی"
    if "عضو" in r:
        return "عضو هیئت مدیره"
    return r or "نامشخص"

# -------------------------
# تحلیل (fallback heuristic ساده و قابل توسعه)
# -------------------------
def parse_ad_heuristic(ad: dict) -> list:
    """
    ورودی: رکورد آگهی (با کلیدهایی مثل 'متن آگهی','تاریخ روزنامه','شماره روزنامه','نام شرکت'...)
    خروجی: لیستی از دیکشنری اعضا استخراج‌شده
    """
    text = normalize_text(ad.get("متن آگهی") or ad.get("text") or "")
    company = normalize_text(ad.get("نام شرکت") or "")
    company_id = normalize_text(ad.get("شناسه ملی شرکت") or "")
    news_no = normalize_text(ad.get("شماره روزنامه") or "")
    date_raw = normalize_text(ad.get("تاریخ روزنامه") or ad.get("تاریخ نامه") or "")

    members = []
    # سعی به یافتن جملات شامل 'آقای' یا 'خانم' یا 'شرکت' یا 'موسسه'
    # الگوهای مختلف را امتحان می‌کنیم
    # 1) اسم با الگو "آقای <name> به شماره ملی <nid> به سمت <role> ..."
    p = re.compile(r"(آقای|خانم)\s+([آ-ی\s\-]{2,60})(?:\s*(?:به شماره ملی|به شماره)\s*(\d{10}))?(?:\s*،|\s*;|\.|\s)*(?:[^،\n]{0,10})?(?:به سمت|بسمت|به‌عنوان|به عنوان|به سمت)\s*([^،\n\.]+)?", flags=re.IGNORECASE)
    for m in p.finditer(text):
        title = m.group(1)
        name = normalize_name(m.group(2))
        nid = m.group(3) or extract_national_id(m.group(0))
        role_raw = m.group(4) or ""
        role_std = standardize_role(role_raw)
        members.append({
            "company_name": company,
            "company_national_id": company_id,
            "name": name,
            "national_id": nid,
            "role_raw": normalize_text(role_raw),
            "role_standard": role_std,
            "start_date_jalali": date_raw,
            "end_date_jalali": None,
            "start_date": shamsi_to_gregorian_safe(date_raw),
            "end_date": None,
            "newspaper_no": news_no
        })

    # اگر هیچ عضوی پیدا نشد، جستجوی عام‌تری روی عبارات 'مدیرعامل','رئیس','نایب','بازرس' داشته باش
    if not members:
        for role_keyword in ["مدیرعامل","رئیس","نایب","نائب","بازرس","عضو","موسسه","مؤسسه"]:
            if role_keyword in text:
                # سعی استخراج نام نزدیک به آن
                m2 = re.search(r"([آ-ی\s\-]{2,60})\s*(?:به شماره ملی\s*(\d{10}))?\s*(?:،|\n|\.|$)", text)
                name = normalize_name(m2.group(1)) if m2 else ""
                nid = m2.group(2) if m2 and m2.group(2) else extract_national_id(text)
                role_std = standardize_role(role_keyword)
                members.append({
                    "company_name": company,
                    "company_national_id": company_id,
                    "name": name,
                    "national_id": nid,
                    "role_raw": role_keyword,
                    "role_standard": role_std,
                    "start_date_jalali": date_raw,
                    "end_date_jalali": None,
                    "start_date": shamsi_to_gregorian_safe(date_raw),
                    "end_date": None,
                    "newspaper_no": news_no
                })
                break

    return members

# -------------------------
# پردازش مجموعه آگهی‌ها
# -------------------------
def process_ads(ads: list) -> pd.DataFrame:
    rows = []
    for ad in ads:
        try:
            found = parse_ad_heuristic(ad)
            for r in found:
                rows.append(r)
        except Exception as e:
            # نادیده گرفتن رکورد مشکل‌دار ولی لاگ کردن در console
            print("Parse error:", e)
    df = pd.DataFrame(rows)
    # افقایم کردن ستون‌ها
    if not df.empty:
        # نمایش تاریخ شمسی برای جدول
        df["start_date_jalali_display"] = df.apply(
            lambda x: x["start_date_jalali"] if x.get("start_date_jalali") else gregorian_to_jalali_str(x.get("start_date")),
            axis=1
        )
        df["end_date_jalali_display"] = df.apply(
            lambda x: x["end_date_jalali"] if x.get("end_date_jalali") else (gregorian_to_jalali_str(x.get("end_date")) if x.get("end_date") else None),
            axis=1
        )
    return df

# -------------------------
# نمودارها (دو نمودار جدا) و دکمه دانلود PNG
# -------------------------
def make_timeline_fig(df: pd.DataFrame, filter_roles: list = None, title: str = "تایم‌لاین", height: int = 600):
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title="داده‌ای برای نمایش وجود ندارد")
        return fig
    dff = df.copy()
    if filter_roles:
        dff = dff[dff["role_standard"].isin(filter_roles)]
    # تهیه محور زمان: اگر start_date خالی باشد از امروز استفاده می‌کنیم ولی در جدول نشان نمی‌دهیم
    dff["start_plot"] = dff["start_date"].apply(lambda x: x if x is not None else datetime.now())
    dff["end_plot"] = dff["end_date"].apply(lambda x: x if x is not None else datetime.now())
    # هر ردیف یک trace جدا (تا قابل هایلایت باشد)
    fig = go.Figure()
    for _, r in dff.iterrows():
        name_label = f"{r.get('name') or '—'} — {r.get('role_standard') or '—'}"
        start = r["start_plot"]
        end = r["end_plot"]
        hover = "<b>%s</b><br>سمت: %s<br>شروع (شمسی): %s<br>پایان (شمسی): %s<br>شماره روزنامه: %s" % (
            r.get("name") or "—",
            r.get("role_standard") or "—",
            r.get("start_date_jalali_display") or "—",
            r.get("end_date_jalali_display") or "—",
            r.get("newspaper_no") or "—"
        )
        fig.add_trace(go.Scatter(
            x=[start, end],
            y=[name_label, name_label],
            mode="lines+markers",
            marker=dict(size=8),
            line=dict(width=8),
            hovertemplate=hover+"<extra></extra>",
            name=name_label,
            showlegend=False
        ))
    fig.update_layout(title=title, template="plotly_white", height=height)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="زمان")
    return fig

def fig_to_png_bytes(fig):
    # از kaleido استفاده می‌کند
    try:
        img_bytes = pio.to_image(fig, format="png", scale=2)
        return img_bytes
    except Exception as e:
        st.error("خطا در ساخت تصویر (kaleido لازم است): " + str(e))
        return None

# -------------------------
# UI — آپلود و پردازش
# -------------------------
st.header("📥 بارگذاری فایل JSON آگهی‌ها")
uploaded = st.file_uploader("فایل JSON را انتخاب کنید (میتواند حاوی چند شرکت باشد)", type=["json"])
if uploaded:
    ads = json.load(uploaded)
    st.success(f"✔ {len(ads)} آگهی بارگذاری شد")

    if st.checkbox("نمایش جدول آگهی‌ها (پیش‌نمایش)"):
        st.dataframe(pd.DataFrame(ads).head(50))

    if st.button("▶️ اجرای تحلیل هوشمند"):
        with st.spinner("در حال تحلیل..."):
            df = process_ads(ads)

        st.success("✅ تحلیل انجام شد")
        # نمایش جدول نهایی با تاریخ شمسی
        if df.empty:
            st.warning("هیچ عضوی استخراج نشد.")
        else:
            # جدول (فیلتر ساده)
            st.markdown("### 🔎 نتایج استخراج‌شده")
            name_filter = st.text_input("فیلتر بر اساس نام (قسمتی از نام):", value="")
            role_filter = st.selectbox("فیلتر بر اساس سمت (اختیاری):", options=[""] + sorted(df["role_standard"].dropna().unique().tolist()))
            df_show = df.copy()
            if name_filter:
                df_show = df_show[df_show["name"].str.contains(normalize_text(name_filter), na=False)]
            if role_filter:
                if role_filter != "":
                    df_show = df_show[df_show["role_standard"] == role_filter]
            # نمایش ستون‌های مهم
            display_cols = ["company_name","company_national_id","name","national_id","role_raw","role_standard","start_date_jalali_display","end_date_jalali_display","newspaper_no"]
            st.dataframe(df_show[display_cols].rename(columns={
                "company_name":"شرکت",
                "company_national_id":"شناسه ملی شرکت",
                "name":"نام",
                "national_id":"کدملی",
                "role_raw":"سمت (خام)",
                "role_standard":"سمت (استاندارد)",
                "start_date_jalali_display":"شروع (شمسی)",
                "end_date_jalali_display":"پایان (شمسی)",
                "newspaper_no":"شماره روزنامه"
            }))

            # دانلود JSON و Excel
            out_json = df.to_json(orient="records", force_ascii=False)
            st.download_button("📥 دانلود JSON استخراج‌شده", data=out_json, file_name="extracted_members.json", mime="application/json")

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="members")
            towrite.seek(0)
            st.download_button("📊 دانلود Excel", data=towrite, file_name="extracted_members.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("---")
            st.markdown("## 📈 نمودار ۱ — تایم‌لاین اعضای کلیدی (مستقل)")
            key_roles = ["مدیرعامل","رئیس هیئت مدیره","نایب رئیس هیئت مدیره"]
            fig_key = make_timeline_fig(df, filter_roles=key_roles, title="تایم‌لاین — اعضای کلیدی", height=500)
            st.plotly_chart(fig_key, use_container_width=True)
            # دانلود PNG نمودار کلیدی
            png_key = fig_to_png_bytes(fig_key)
            if png_key:
                st.download_button("📥 دانلود تصویر نمودار اعضای کلیدی (PNG)", data=png_key, file_name="timeline_key.png", mime="image/png")

            st.markdown("## 📈 نمودار ۲ — تایم‌لاین همه اعضا (مستقل)")
            fig_all = make_timeline_fig(df, filter_roles=None, title="تایم‌لاین — همه اعضا", height=700)
            st.plotly_chart(fig_all, use_container_width=True)
            png_all = fig_to_png_bytes(fig_all)
            if png_all:
                st.download_button("📥 دانلود تصویر نمودار همه اعضا (PNG)", data=png_all, file_name="timeline_all.png", mime="image/png")

st.markdown("</div>", unsafe_allow_html=True)
