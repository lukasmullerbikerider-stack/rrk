
import streamlit as st
import json
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# تنظیمات صفحه
st.set_page_config(
    page_title="تایم‌لاین اعضای شرکت",
    page_icon="🏢",
    layout="wide"
)

# استایل CSS برای راست به چپ
st.markdown("""
<style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
    .main .block-container {
        direction: rtl;
    }
    div[data-testid="stMetricValue"] {
        direction: rtl;
    }
    .stTabs [data-baseweb="tab-list"] {
        direction: rtl;
    }
    h1, h2, h3 {
        font-family: 'Vazir', 'Tahoma', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

def process_members(members_data):
    """پردازش و گروه‌بندی اعضا"""
    member_dict = {}
    
    for member in members_data:
        key = member.get('کد ملی') or member.get('نام')
        
        if key not in member_dict:
            member_dict[key] = {
                'نام': member['نام'],
                'کد ملی': member.get('کد ملی', 'نامشخص'),
                'سمت‌ها': []
            }
        
        # تعیین دسته‌بندی
        سمت = member.get('سمت_دقیق', '')
        if 'بازرس' in سمت:
            category = 'نظارت'
        elif any(x in سمت for x in ['مدیرعامل', 'رئیس', 'نایب']):
            category = 'مدیریت'
        else:
            category = 'هیئت مدیره'
        
        member_dict[key]['سمت‌ها'].append({
            'سمت': member.get('سمت_استاندارد', member.get('سمت_دقیق')),
            'تاریخ شروع': member.get('تاریخ شروع'),
            'تاریخ پایان': member.get('تاریخ پایان'),
            'دسته': category,
            'شماره روزنامه': member.get('شماره روزنامه')
        })
    
    return list(member_dict.values())

def get_color_by_category(category):
    """تعیین رنگ بر اساس دسته"""
    colors = {
        'مدیریت': '#3B82F6',
        'هیئت مدیره': '#10B981',
        'نظارت': '#8B5CF6'
    }
    return colors.get(category, '#6B7280')

def get_color_by_role(role):
    """تعیین رنگ بر اساس سمت"""
    if 'رئیس' in role and 'نایب' not in role:
        return '#EF4444'
    elif 'نایب' in role:
        return '#F97316'
    elif 'مدیرعامل' in role:
        return '#2563EB'
    elif 'بازرس اصلی' in role:
        return '#7C3AED'
    elif 'بازرس' in role:
        return '#A78BFA'
    return '#10B981'

def create_timeline_chart(members, color_mode='category'):
    """ایجاد نمودار تایم‌لاین"""
    data = []
    
    for member in members:
        for position in member['سمت‌ها']:
            data.append({
                'نام': member['نام'],
                'سمت': position['سمت'],
                'شروع': position['تاریخ شروع'],
                'پایان': position['تاریخ پایان'],
                'دسته': position['دسته']
            })
    
    df = pd.DataFrame(data)
    
    # تبدیل تاریخ شمسی به میلادی برای نمودار (تقریبی)
    def shamsi_to_timestamp(date_str):
        if not date_str:
            return None
        try:
            parts = date_str.split('/')
            year = int(parts[0]) + 621  # تبدیل تقریبی
            month = int(parts[1])
            day = int(parts[2])
            return f"{year}-{month:02d}-{day:02d}"
        except:
            return None
    
    df['Start'] = df['شروع'].apply(shamsi_to_timestamp)
    df['Finish'] = df['پایان'].apply(shamsi_to_timestamp)
    
    # ایجاد نمودار Gantt
    if color_mode == 'category':
        color_col = 'دسته'
        colors = {'مدیریت': '#3B82F6', 'هیئت مدیره': '#10B981', 'نظارت': '#8B5CF6'}
    else:
        color_col = 'سمت'
        colors = None
    
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="Finish", 
        y="نام", 
        color=color_col,
        hover_data=['سمت', 'شروع', 'پایان'],
        title='',
        color_discrete_map=colors
    )
    
    fig.update_layout(
        height=max(400, len(members) * 50),
        xaxis_title='',
        yaxis_title='',
        showlegend=True,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Tahoma, Vazir"),
        yaxis={'categoryorder': 'total ascending'}
    )
    
    return fig

# عنوان اصلی
st.title("🏢 تایم‌لاین اعضای شرکت")
st.markdown("---")

# آپلود فایل
uploaded_file = st.file_uploader(
    "📁 فایل JSON اطلاعات شرکت را آپلود کنید",
    type=['json'],
    help="فایل JSON باید شامل نام شرکت، شناسه و لیست اعضا باشد"
)

if uploaded_file is not None:
    try:
        # خواندن فایل
        company_data = json.load(uploaded_file)
        
        # بررسی ساختار
        if 'نام شرکت' not in company_data or 'اعضای شرکت' not in company_data:
            st.error("❌ فرمت فایل صحیح نیست. لطفاً فایل JSON با فرمت صحیح آپلود کنید.")
            st.stop()
        
        # نمایش اطلاعات شرکت
        st.success(f"✅ فایل با موفقیت بارگذاری شد")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header(f"🏢 {company_data['نام شرکت']}")
        with col2:
            st.metric("شناسه شرکت", company_data.get('شناسه شرکت', 'نامشخص'))
        
        st.markdown("---")
        
        # پردازش اعضا
        members = process_members(company_data['اعضای شرکت'])
        key_members = [m for m in members if any(p['دسته'] == 'مدیریت' for p in m['سمت‌ها'])]
        
        # نمایش آمار
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 تعداد کل اعضا", len(members))
        with col2:
            st.metric("👔 مدیران کلیدی", len(key_members))
        with col3:
            total_positions = sum(len(m['سمت‌ها']) for m in members)
            st.metric("📋 مجموع سمت‌ها", total_positions)
        
        st.markdown("---")
        
        # تب‌های اصلی
        tab1, tab2, tab3 = st.tabs(["📈 نمودار تایم‌لاین", "👥 اعضای کلیدی", "📋 همه اعضا"])
        
        with tab1:
            st.subheader("نمودار تایم‌لاین اعضا")
            
            col1, col2 = st.columns(2)
            with col1:
                view_mode = st.radio(
                    "نمایش:",
                    ["همه اعضا", "فقط مدیران"],
                    horizontal=True
                )
            with col2:
                color_mode = st.radio(
                    "رنگ‌بندی:",
                    ["بر اساس دسته", "بر اساس سمت"],
                    horizontal=True
                )
            
            display_members = key_members if view_mode == "فقط مدیران" else members
            color_type = 'category' if color_mode == "بر اساس دسته" else 'role'
            
            if display_members:
                fig = create_timeline_chart(display_members, color_type)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("⚠️ داده‌ای برای نمایش وجود ندارد")
        
        with tab2:
            st.subheader("👔 اعضای کلیدی (مدیران)")
            
            if not key_members:
                st.warning("⚠️ عضو کلیدی یافت نشد")
            else:
                for member in key_members:
                    with st.expander(f"**{member['نام']}** - کد ملی: {member['کد ملی']}"):
                        for i, pos in enumerate(member['سمت‌ها'], 1):
                            color = get_color_by_role(pos['سمت'])
                            st.markdown(f"""
                            <div style='background-color: {color}20; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-right: 4px solid {color}'>
                                <strong style='color: {color}; font-size: 16px;'>سمت {i}: {pos['سمت']}</strong><br>
                                📅 <strong>تاریخ:</strong> {pos['تاریخ شروع']} تا {pos['تاریخ پایان']}<br>
                                🏷️ <strong>دسته:</strong> {pos['دسته']}<br>
                                📰 <strong>روزنامه:</strong> {pos['شماره روزنامه']}
                            </div>
                            """, unsafe_allow_html=True)
        
        with tab3:
            st.subheader("📋 همه اعضای شرکت")
            
            # فیلتر بر اساس دسته
            categories = ['همه'] + list(set(p['دسته'] for m in members for p in m['سمت‌ها']))
            selected_category = st.selectbox("🔍 فیلتر بر اساس دسته:", categories)
            
            filtered_members = members
            if selected_category != 'همه':
                filtered_members = [
                    m for m in members 
                    if any(p['دسته'] == selected_category for p in m['سمت‌ها'])
                ]
            
            # جستجو
            search_term = st.text_input("🔎 جستجوی نام عضو:", "")
            if search_term:
                filtered_members = [
                    m for m in filtered_members 
                    if search_term in m['نام']
                ]
            
            st.write(f"**تعداد نتایج:** {len(filtered_members)} عضو")
            
            for member in filtered_members:
                with st.expander(f"**{member['نام']}** - کد ملی: {member['کد ملی']} ({len(member['سمت‌ها'])} سمت)"):
                    for i, pos in enumerate(member['سمت‌ها'], 1):
                        color = get_color_by_category(pos['دسته'])
                        st.markdown(f"""
                        <div style='background-color: {color}20; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-right: 4px solid {color}'>
                            <strong style='color: {color}; font-size: 16px;'>سمت {i}: {pos['سمت']}</strong><br>
                            📅 <strong>تاریخ:</strong> {pos['تاریخ شروع']} تا {pos['تاریخ پایان']}<br>
                            🏷️ <strong>دسته:</strong> {pos['دسته']}<br>
                            📰 <strong>روزنامه:</strong> {pos['شماره روزنامه']}
                        </div>
                        """, unsafe_allow_html=True)
        
        # دانلود گزارش
        st.markdown("---")
        st.subheader("📥 دانلود گزارش")
        
        # تبدیل به DataFrame برای دانلود
        report_data = []
        for member in members:
            for pos in member['سمت‌ها']:
                report_data.append({
                    'نام': member['نام'],
                    'کد ملی': member['کد ملی'],
                    'سمت': pos['سمت'],
                    'تاریخ شروع': pos['تاریخ شروع'],
                    'تاریخ پایان': pos['تاریخ پایان'],
                    'دسته': pos['دسته'],
                    'شماره روزنامه': pos['شماره روزنامه']
                })
        
        df_report = pd.DataFrame(report_data)
        
        col1, col2 = st.columns(2)
        with col1:
            csv = df_report.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📊 دانلود گزارش CSV",
                data=csv,
                file_name=f"report_{company_data['نام شرکت']}.csv",
                mime="text/csv"
            )
        with col2:
            excel_buffer = pd.ExcelWriter('temp.xlsx', engine='xlsxwriter')
            df_report.to_excel(excel_buffer, index=False, sheet_name='گزارش')
            excel_buffer.close()
            
        
    except json.JSONDecodeError:
        st.error("❌ خطا در خواندن فایل JSON. لطفاً یک فایل معتبر آپلود کنید.")
    except Exception as e:
        st.error(f"❌ خطا: {str(e)}")
        
else:
    # راهنمای فرمت فایل
    st.info("👆 لطفاً فایل JSON خود را آپلود کنید")
    
    st.markdown("### 📝 فرمت فایل JSON:")
    st.code("""
{
  "نام شرکت": "نام شرکت",
  "شناسه شرکت": "شناسه",
  "اعضای شرکت": [
    {
      "نام": "نام عضو",
      "کد ملی": "کد ملی",
      "سمت_دقیق": "سمت دقیق",
      "سمت_استاندارد": "سمت استاندارد",
      "تاریخ شروع": "1403/01/01",
      "تاریخ پایان": "1405/01/01",
      "شماره روزنامه": "12345"
    }
  ]
}
    """, language='json')
    
    st.markdown("### ✨ ویژگی‌های برنامه:")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        - 📊 نمودار تایم‌لاین تعاملی
        - 👥 نمایش اعضای کلیدی
        - 📋 لیست کامل همه اعضا
        - 🔍 جستجو و فیلتر
        """)
    with col2:
        st.markdown("""
        - 🎨 رنگ‌بندی بر اساس سمت/دسته
        - 📥 دانلود گزارش (CSV/Excel)
        - 📈 آمار و نمودارها
        - 🇮🇷 پشتیبانی کامل از فارسی
        """)

# فوتر
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    ساخته شده با ❤️ برای تحلیل داده‌های شرکت‌ها
</div>
""", unsafe_allow_html=True)
