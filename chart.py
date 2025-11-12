import streamlit as st
import pandas as pd
import plotly.express as px
import json

# -------------------------------------------------------------------
# 📊 تابع نمایش نمودارها
# -------------------------------------------------------------------
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
        
st.set_page_config(page_title="📊 داشبورد اعضا و مدیران شرکت", layout="wide")

# 📁 آپلود فایل JSON
uploaded2 = st.file_uploader("📂 فایل اعضای شرکت", type=["json"], label_visibility="visible")

if uploaded2:
    membersdata = json.load(uploaded2)
    charts_data = membersdata
    charts(charts_data)
