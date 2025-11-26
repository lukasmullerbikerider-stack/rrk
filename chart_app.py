# app.py
import streamlit as st
import json
import pandas as pd
import jdatetime
import datetime
import plotly.express as px
from io import BytesIO
from fpdf import FPDF

st.set_page_config(page_title="تایم‌لاین اعضا (شمسی) — Gantt", layout="wide")
st.markdown(
    """
    <style>
    /* راست‌چین کلی صفحه */
    html, body, .stApp { direction: rtl; text-align: right; }
    /* فونت پیش‌فرض (در صورت نصب نبودن فونت محلی، مرورگر فونت پیش‌فرض را استفاده می‌کند) */
    .title { font-weight: 700; font-size: 1.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">سامانه نمایش تایم‌لاین اعضا — Gantt (تماماً شمسی)</div>', unsafe_allow_html=True)
st.write("این اپ: فایل JSON را می‌گیرد، تاریخ‌ها را به صورت شمسی نشان می‌دهد و نمودار Gantt قابل دانلود تولید می‌کند.")

# -------------------------
# Utilities: parse jalali date
# -------------------------
def parse_jalali_date(s):
    if not s or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip()
    # معمولاً فرمت‌ها مانند: 1403/11/23 یا 24/12/1401 یا 09/06/1400
    # جداکننده‌ها ممکن است / یا - یا فاصله باشند
    import re
    parts = re.split(r"[^\d]+", s)
    parts = [p for p in parts if p != ""]
    if len(parts) != 3:
        return None
    # اگر بخش اول 4 رقمی بود => Y/M/D، وگرنه فرض کن D/M/Y
    if len(parts[0]) == 4:
        y, m, d = parts
    elif len(parts[2]) == 4:
        d, m, y = parts
    else:
        # fallback: فرض Y/M/D
        y, m, d = parts
    try:
        y, m, d = int(y), int(m), int(d)
        # create jdatetime.date and convert to gregorian date for plotting
        jdate = jdatetime.date(y, m, d)
        gdate = jdate.togregorian()  # returns datetime.date
        # convert to datetime
        return datetime.datetime(gdate.year, gdate.month, gdate.day)
    except Exception:
        return None

def jalali_str_from_parts(s):
    # دریافت رشته و بازگرداندن رشته شمسی استاندارد YYYY/MM/DD
    if not s or (isinstance(s, float) and pd.isna(s)):
        return ""
    import re
    parts = re.split(r"[^\d]+", str(s).strip())
    parts = [p for p in parts if p != ""]
    if len(parts) != 3:
        return str(s)
    if len(parts[0]) == 4:
        y, m, d = parts
    elif len(parts[2]) == 4:
        d, m, y = parts
    else:
        y, m, d = parts
    # normalize to zero-padded
    try:
        y_i, m_i, d_i = int(y), int(m), int(d)
        return f"{y_i:04d}/{m_i:02d}/{d_i:02d}"
    except:
        return str(s)

# -------------------------
# File uploader
# -------------------------
uploaded = st.file_uploader("بارگذاری فایل JSON روزنامه رسمی", type=["json"])
if not uploaded:
    st.info("لطفاً یک فایل JSON را بارگذاری کنید. ساختار باید مشابه خروجی استخراج‌شده باشد.")
    st.stop()

try:
    data = json.load(uploaded)
except Exception as e:
    st.error("فایل JSON قابل خواندن نیست. خطا: " + str(e))
    st.stop()

# -------------------------
# Normalize into dataframe
# -------------------------
rows = []
for source_key, arr in data.items():
    # اگر ریشه شامل کلیدهای متادیتا باشد مثل نام شرکت، شناسه ملی -> نادیده بگیر
    if not isinstance(arr, list):
        continue
    for item in arr:
        name = item.get("نام", "") or item.get("name", "")
        code = item.get("کد ملی", "") or item.get("id", "")
        role = item.get("سمت", "") or item.get("role", "")
        start_raw = item.get("تاریخ شروع") or item.get("start")
        end_raw = item.get("تاریخ پایان") or item.get("end")
        start_g = parse_jalali_date(start_raw)
        end_g = parse_jalali_date(end_raw) if end_raw else None
        rows.append({
            "نام": name,
            "کد ملی": code,
            "سمت": role,
            "تاریخ شروع (شمسی)": jalali_str_from_parts(start_raw),
            "تاریخ پایان (شمسی)": jalali_str_from_parts(end_raw) if end_raw else "",
            "start_greg": start_g,
            "end_greg": end_g,
            "منبع": source_key
        })

df = pd.DataFrame(rows)
if df.empty:
    st.error("فایلی که بارگذاری کرده‌اید رکورد قابل پردازشی ندارد.")
    st.stop()

# fill missing end_greg with today for plotting purposes (but we will show 'اکنون' to user)
today = datetime.datetime.now()
df["end_greg_plot"] = df["end_greg"].fillna(today)
df["start_greg_plot"] = df["start_greg"].fillna(today)

# -------------------------
# Role color mapping
# -------------------------
roles = df["سمت"].fillna("بدون نقش").unique().tolist()
palette = px.colors.qualitative.Plotly
color_map = {r: palette[i % len(palette)] for i, r in enumerate(sorted(roles))}

# Sidebar filters
st.sidebar.header("فیلترها")
unique_names = df["نام"].dropna().unique().tolist()
selected_names = st.sidebar.multiselect("انتخاب اشخاص (خالی = همه)", unique_names, default=[])

selected_roles = st.sidebar.multiselect("انتخاب نقش‌ها (خالی = همه)", sorted(roles), default=[])
only_core = st.sidebar.checkbox("فقط اعضای اصلی (مدیرعامل، رئیس هیئت مدیره، عضو هیئت مدیره)", value=False)

core_titles = {"مدیرعامل", "رئیس هیئت مدیره", "عضو هیئت مدیره"}
df_plot = df.copy()
if selected_names:
    df_plot = df_plot[df_plot["نام"].isin(selected_names)]
if selected_roles:
    df_plot = df_plot[df_plot["سمت"].isin(selected_roles)]
if only_core:
    df_plot = df_plot[df_plot["سمت"].isin(core_titles)]

# Sort by start date descending so earliest appear at bottom
df_plot = df_plot.sort_values(by=["start_greg_plot", "نام"], ascending=[True, True])

# create Gantt (timeline) using plotly.express
if df_plot.empty:
    st.warning("هیچ رکوردی با فیلترهای انتخاب‌شده باقی نماند.")
    st.stop()

fig = px.timeline(
    df_plot,
    x_start="start_greg_plot",
    x_end="end_greg_plot",
    y="نام",
    color="سمت",
    color_discrete_map=color_map,
    hover_data={"منبع": True, "سمت": True},
    title="نمودار زمانی (Gantt) اعضا"
)

# reverse y to show first person at top (optional)
fig.update_yaxes(autorange="reversed")

# Customize hover to show Jalali dates and not show gregorian
# We'll build a custom hovertemplate per trace
for trace in fig.data:
    # trace.name is the role
    mask = df_plot["سمت"] == trace.name
    # create text with jalali dates for each point
    texts = []
    sub = df_plot[mask]
    # map index order to trace points
    # note: px.timeline organizes segments; lengths should match
    for _, row in sub.iterrows():
        start_j = row["تاریخ شروع (شمسی)"] or "نامشخص"
        end_j = row["تاریخ پایان (شمسی)"] or "اکنون"
        texts.append(
            f"نام: {row['نام']}<br>سمت: {row['سمت']}<br>از: {start_j}<br>تا: {end_j}<br>منبع: {row['منبع']}"
        )
    # assign text and hovertemplate
    # If lengths mismatch, fallback to generic hover
    if len(texts) == len(trace.x):
        trace.text = texts
        trace.hovertemplate = "%{text}<extra></extra>"
    else:
        # fallback: simple hover showing name/role
        trace.hovertemplate = "سمت: %{legendgroup}<br>نام: %{y}<extra></extra>"

# layout tweaks for RTL feel: align title and legend to right
fig.update_layout(
    title_x=0.99,
    legend_title_text="نقش‌ها",
    margin=dict(l=20, r=20, t=60, b=40),
    hoverlabel_align="right"
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------
# Downloads: Excel (with Jalali strings) & PDF (chart image embedded)
# -------------------------
st.markdown("---")
st.header("خروجی‌ها")

# Excel (we produce a sheet including the original jalali strings)
def to_excel_bytes(df_input):
    out = BytesIO()
    df_out = df_input[[
        "نام", "کد ملی", "سمت",
        "تاریخ شروع (شمسی)", "تاریخ پایان (شمسی)", "منبع"
    ]]
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="members")
    return out.getvalue()

excel_bytes = to_excel_bytes(df if df is not None else df_plot)
st.download_button(
    label="دانلود Excel (شامل تاریخ‌های شمسی)",
    data=excel_bytes,
    file_name="members_jalali.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# PDF: render plotly figure to PNG (kaleido) and embed in a single-page PDF
def fig_to_pdf_bytes(fig_obj, title="نمودار تایم‌لاین"):
    # fig.to_image requires kaleido installed
    img_bytes = fig_obj.to_image(format="png", engine="kaleido", width=1400, height=600, scale=2)
    # create PDF and insert image
    pdf = FPDF(orientation="L", unit="pt", format=(1400, 900))
    pdf.add_page()
    # header (rtl)
    pdf.set_font("Arial", size=16)
    pdf.cell(0, 30, txt=title, ln=1, align="R")
    # save image temporarily into BytesIO and add
    pdf.image(BytesIO(img_bytes), x=50, y=80, w=1300)
    out = BytesIO()
    pdf.output(out)
    return out.getvalue()

try:
    pdf_bytes = fig_to_pdf_bytes(fig, title="نمودار تایم‌لاین اعضا (شمسی)")
    st.download_button("دانلود PDF نمودار", data=pdf_bytes, file_name="timeline_chart.pdf", mime="application/pdf")
except Exception as e:
    st.error("ایجاد PDF نیاز به کتابخانه kaleido/کتابخانه‌های گرافیکی دارد یا خطایی رخ داده: " + str(e))
    st.info("برای خروجی PDF مطمئن شو که بسته 'kaleido' نصب است و یا به صورت محلی اجرا کن.")

st.success("تمام تاریخ‌ها در رابط کاربری و فایل‌های خروجی به فرمت شمسی (YYYY/MM/DD) نمایش داده می‌شوند. هیچ تاریخ میلادی به کاربر نمایش داده نمی‌شود.")
