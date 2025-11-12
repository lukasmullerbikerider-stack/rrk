import streamlit as st
import pandas as pd
import plotly.express as px
import json
import jdatetime  # برای تبدیل تاریخ شمسی به میلادی

# ---------------------- پیکربندی صفحه ----------------------
st.set_page_config(page_title="📊 داشبورد اعضا و مدیران شرکت", layout="wide")

st.title("📊 داشبورد تحلیلی اعضا و مدیران شرکت")
st.caption("بارگذاری فایل JSON اعضای شرکت و مشاهده‌ی تایم‌لاین تغییرات سمت‌ها در طول زمان")

# ---------------------- آپلود فایل JSON ----------------------
uploaded2 = st.file_uploader("📂 فایل اعضای شرکت", type=["json"], label_visibility="visible")

# ---------------------- تابع اصلی ----------------------
def charts(data):
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
    df = df.fillna("نامشخص")

    # ✅ 2. تبدیل تاریخ شمسی به میلادی برای محور زمان
    def persian_to_gregorian(date_str):
        try:
            if not isinstance(date_str, str):
                return None
            # برای مواردی مثل "تا پایان سال مالی 1404"
            if "تا پایان" in date_str:
                year = int("".join(filter(str.isdigit, date_str)))
                return jdatetime.date(year, 12, 29).togregorian()
            y, m, d = map(int, date_str.split("/"))
            return jdatetime.date(y, m, d).togregorian()
        except:
            return None

    df["start"] = df["تاریخ شروع"].apply(persian_to_gregorian)
    df["end"] = df["تاریخ پایان"].apply(persian_to_gregorian)

    # 🌈 CSS استایل کارت‌ها
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
    # 🟦 نمودار اول: مدیرعامل، رئیس و نایب‌رئیس هیئت مدیره
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👔 مدیرعامل و اعضای ارشد (Timeline)")
        st.markdown("<p>نمودار تایم‌لاین مدیرعامل، رئیس و نایب‌رئیس هیئت مدیره در طول زمان.</p>", unsafe_allow_html=True)

        top_roles = ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره"]
        df_top = df[df["سمت"].apply(lambda x: any(r in x for r in top_roles))].copy()

        if not df_top.empty:
            fig_timeline_top = px.timeline(
                df_top,
                x_start="start",
                x_end="end",
                y="نام",
                color="سمت",
                hover_data=["وضعیت", "شماره روزنامه"],
                title="📅 تایم‌لاین مدیرعامل، رئیس و نایب‌رئیس هیئت مدیره"
            )
            fig_timeline_top.update_yaxes(autorange="reversed")
            fig_timeline_top.update_layout(
                xaxis_title="تاریخ",
                yaxis_title="اعضا",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_timeline_top, use_container_width=True)
        else:
            st.warning("⚠️ داده‌ای برای مدیرعامل یا هیئت مدیره یافت نشد.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 🟨 نمودار دوم: همه اعضای شرکت (Timeline کلی)
    # ------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👥 تمامی اعضای شرکت در گذر زمان")
        st.markdown("<p>این نمودار تمام اعضا (از جمله بازرسان و مدیران) را در بازه‌های زمانی نمایش می‌دهد.</p>", unsafe_allow_html=True)

        if not df.empty:
            fig_timeline_all = px.timeline(
                df,
                x_start="start",
                x_end="end",
                y="نام",
                color="سمت",
                hover_data=["وضعیت", "شماره روزنامه"],
                title="📅 تایم‌لاین کلی اعضای شرکت"
            )
            fig_timeline_all.update_yaxes(autorange="reversed")
            fig_timeline_all.update_layout(
                xaxis_title="بازه زمانی",
                yaxis_title="اعضا",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_timeline_all, use_container_width=True)
        else:
            st.warning("⚠️ داده‌ای برای رسم نمودار یافت نشد.")

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
