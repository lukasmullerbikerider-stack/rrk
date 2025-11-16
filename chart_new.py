import streamlit as st
import pandas as pd
import plotly.express as px
import json
import jdatetime

st.set_page_config(page_title="📊 داشبورد اعضا و مدیران شرکت", layout="wide")

st.title("📊 داشبورد تحلیلی اعضا و مدیران شرکت")
st.caption("بارگذاری فایل JSON اعضای شرکت و مشاهده‌ی تایم‌لاین تغییرات سمت‌ها در طول زمان")

uploaded2 = st.file_uploader("📂 فایل اعضای شرکت", type=["json"], label_visibility="visible")

# ---------------------- تابع تبدیل فایل به ساختار یکپارچه ----------------------
def normalize_members(data):
    # اگر فرمت به صورت آرایه باشد → تبدیلش می‌کنیم به یک دیکشنری استاندارد
    if isinstance(data, list):
        return {
            "اعضای فعلی شرکت": data,
            "اعضای سابق شرکت": []
        }
    return data

# ---------------------- تابع اصلی ----------------------
def charts(data):
    data = normalize_members(data)

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
    df = df.fillna("نامشخص")

    # --- تبدیل تاریخ ---
    def persian_to_gregorian(date_str):
        try:
            if not isinstance(date_str, str):
                return None
            if "تا پایان" in date_str:
                year = int("".join(filter(str.isdigit, date_str)))
                return jdatetime.date(year, 12, 29).togregorian()
            y, m, d = map(int, date_str.split("/"))
            return jdatetime.date(y, m, d).togregorian()
        except:
            return None

    # سازگاری با نام ستون‌های فایل شما
    if "تاریخ شروع" not in df.columns and "تاریخ شروع سمت" in df.columns:
        df["تاریخ شروع"] = df["تاریخ شروع سمت"]

    if "تاریخ پایان" not in df.columns and "تاریخ پایان سمت" in df.columns:
        df["تاریخ پایان"] = df["تاریخ پایان سمت"]

    df["start"] = df["تاریخ شروع"].apply(persian_to_gregorian)
    df["end"] = df["تاریخ پایان"].apply(persian_to_gregorian)

    # ---- ظاهر کارت‌ها ----
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

    # ------------------------------------------------------------------
    # 🟦 نمودار نقش‌های ارشد: مدیرعامل + رئیس + نایب‌رییس
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👔 مدیرعامل و اعضای ارشد (Timeline)")

        top_roles = ["مدیرعامل", "مدیر عامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره"]
        df_top = df[df["سمت"].apply(lambda x: any(r in str(x) for r in top_roles))]

        if not df_top.empty:
            fig = px.timeline(
                df_top,
                x_start="start",
                x_end="end",
                y="نام فرد",
                color="سمت",
                hover_data=["وضعیت", "شماره روزنامه"],
                title="📅 تایم‌لاین سمت‌های ارشد"
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ هیچ داده‌ای برای سمت‌های ارشد یافت نشد.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 🟨 نمودار کلی همه اعضا
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👥 تمامی اعضای شرکت در گذر زمان")

        if not df.empty:
            fig_all = px.timeline(
                df,
                x_start="start",
                x_end="end",
                y="نام فرد",
                color="سمت",
                hover_data=["وضعیت", "شماره روزنامه"],
                title="📅 تایم‌لاین کلی اعضا"
            )
            fig_all.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_all, use_container_width=True)
        else:
            st.warning("⚠️ دیتایی برای رسم نمودار وجود ندارد.")

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------- اجرای تابع ----------------------
if uploaded2:
    try:
        membersdata = json.load(uploaded2)
        charts(membersdata)
    except Exception as e:
        st.error(f"❌ خطا در خواندن فایل JSON: {e}")
else:
    st.info("برای شروع، فایل JSON اعضای شرکت را بارگذاری کنید.")
