import os
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
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from jdatetime import datetime as jdatetime
# ----------------------------------
# تنظیمات عمومی
# ----------------------------------
st.set_page_config(page_title="RRK Company Extractor", page_icon="🏢", layout="wide")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

chrome_options = Options()
#chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1400,1000")
chrome_options.add_argument("--disable-notifications")

# ----------------------------------
# توابع Selenium
# ----------------------------------
def scrape_company_ads(query):
    """جمع‌آوری آگهی‌های rrk.ir"""
    driver, wait = setup_driver()
    ad_data = []

    try:
        driver.get("https://www.rrk.ir/")
        search_box = wait.until(EC.presence_of_element_located((By.ID, "P0_SEARCH_ITEM")))
        search_box.clear()
        search_box.send_keys(query)
        driver.find_element(By.ID, "BTN_ADVANCEDSEARCH").click()
        time.sleep(3)

        # ورود به بخش آگهی‌ها
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "t-LinksList-link"))).click()
        time.sleep(5)

        current_page = 1
        while True:
            ad_links = get_links(driver)
            if not ad_links:
                break

            for tag in ad_links:
                href = tag.get("href")
                if not href.startswith("/ords/r/rrs/rrs-front/f-detail-ad"):
                    continue
                url = "https://rrk.ir" + href

                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(url)
                soup = BeautifulSoup(driver.page_source, "html.parser")

                try:
                    data = extract_fields(driver, soup)
                    data["url"] = url
                    ad_data.append(data)
                except Exception as e:
                    logging.warning(f"⚠️ خطا در استخراج آگهی: {e}")
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(2)

            # صفحه بعد
            next_buttons = driver.find_elements(By.CSS_SELECTOR, "ul.a-GV-pageSelector-list li button.a-GV-pageButton")
            next_btn = next((b for b in next_buttons if b.text.isdigit() and int(b.text) == current_page + 1), None)
            if not next_btn:
                break
            driver.execute_script("arguments[0].click();", next_btn)
            current_page += 1
            time.sleep(5)

    except Exception as e:
        logging.error(f"❌ خطا: {e}")
    finally:
        driver.quit()

    return ad_data

def setup_driver():
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    wait = WebDriverWait(driver, 60)
    return driver, wait

def get_links(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    return soup.select("a[href*='/ords/r/rrs/rrs-front/f-detail-ad']")

def extract_fields(driver, soup):
    """استخراج فیلدهای آگهی از صفحه جزئیات"""
    fields = {
        "شماره پیگیری": driver.find_element(By.ID, "P28_REFERENCENUMBER").get_attribute("value"),
        "شماره نامه": driver.find_element(By.ID, "P28_INDIKATORNUMBER").get_attribute("value"),
        "تاریخ نامه": driver.find_element(By.ID, "P28_SABTDATE").get_attribute("value"),
        "نام شرکت": driver.find_element(By.ID, "P28_COMPANYNAME").get_attribute("value"),
        "شناسه ملی شرکت": driver.find_element(By.ID, "P28_SABTNATIONALID").get_attribute("value"),
        "شماره ثبت": driver.find_element(By.ID, "P28_SABTNUMBER").get_attribute("value"),
        "شماره روزنامه": driver.find_element(By.ID, "P28_NEWSPAPERNO").get_attribute("value"),
        "تاریخ روزنامه": driver.find_element(By.ID, "P28_NEWSPAPERDATE").get_attribute("value"),
        "شماره صفحه روزنامه": driver.find_element(By.ID, "P28_PAGENUMBER").get_attribute("value"),
        "تعداد نوبت انتشار": driver.find_element(By.ID, "P28_HCNEWSSTAGE").get_attribute("value")
    }
    dynamic = soup.select_one("a-dynamic-content")
    fields["متن آگهی"] = dynamic.get_text(" ", strip=True) if dynamic else soup.get_text(" ", strip=True)
    return fields

def llm(data):
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
        model_name="gemini-2.5-pro",
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

    # 8️⃣ --- چاپ خلاصه در کنسول ---
    print("✅ تحلیل با موفقیت انجام شد.")
    print(f"📁 خروجی ذخیره شد در: {output_path}")

# تبدیل تاریخ شمسی به میلادی
def shamsi_to_miladi(date_str):
    """تبدیل تاریخ شمسی به میلادی"""
    if date_str is None or date_str == 'null':
        return datetime.now()

    try:
        parts = date_str.split('/')
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        j_date = jdatetime.date(year, month, day)
        return j_date.togregorian()
    except Exception as e:
        return datetime.now()

def charts(data):
    # بررسی اینکه داده‌ها به درستی دریافت شده‌اند
    if not data or 'اعضای سابق شرکت' not in data:
        print("❌ داده‌ها معتبر نیستند.")
        return
    
    members = data['اعضای سابق شرکت']
    
    # تبدیل داده‌ها به DataFrame
    df = pd.DataFrame(members)
    
    # اطمینان از تبدیل درست تاریخ‌ها
    df['تاریخ_شروع_میلادی'] = df['تاریخ شروع'].apply(shamsi_to_miladi)
    df['تاریخ_پایان_میلادی'] = df['تاریخ پایان'].apply(shamsi_to_miladi)

    # دسته‌بندی اعضا بر اساس سمت
    def categorize_position(position):
        """دسته‌بندی سمت‌ها"""
        if 'مدیرعامل' in position:
            return 'مدیرعامل'
        elif any(x in position for x in ['رئیس هیئت', 'رئیس هیات', 'نایب', 'نائب', 'عضو هیئت', 'عضو هیات']):
            return 'هیئت مدیره'
        elif 'بازرس' in position:
            return 'بازرس'
        else:
            return 'سایر'

    df['دسته'] = df['سمت'].apply(categorize_position)
    df = df.sort_values('تاریخ_شروع_میلادی')

    # ایجاد داشبورد با Plotly
    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.5, 0.3, 0.2],
        subplot_titles=(
            'تایم‌لاین کامل اعضای شرکت',
            'تایم‌لاین رئیس هیئت مدیره و مدیرعامل',
            'آمار سمت‌ها'
        ),
        specs=[[{"type": "scatter"}],
            [{"type": "scatter"}],
            [{"type": "bar"}]],
        vertical_spacing=0.12
    )

    # رنگ‌بندی برای سمت‌های مختلف
    color_map = {
        'رئیس هیئت مدیره': '#1f77b4',
        'رئیس هیات مدیره': '#1f77b4',
        'مدیرعامل': '#ff7f0e',
        'نایب رئیس هیئت مدیره': '#2ca02c',
        'نائب رئیس هیئت مدیره': '#2ca02c',
        'نائب رئیس هیات مدیره': '#2ca02c',
        'عضو اصلی هیئت مدیره': '#d62728',
        'عضو هیئت مدیره': '#9467bd',
        'عضو هیات مدیره': '#9467bd',
        'بازرس اصلی': '#8c564b',
        'بازرس علی البدل': '#e377c2'
    }

    # نمودار 1: تایم‌لاین کامل
    for idx, row in df.iterrows():
        color = color_map.get(row['سمت'], '#7f7f7f')

        fig.add_trace(
            go.Scatter(
                x=[row['تاریخ_شروع_میلادی'], row['تاریخ_پایان_میلادی']],
                y=[row['نام'], row['نام']],
                mode='lines+markers',
                name=row['سمت'],
                line=dict(color=color, width=6),
                marker=dict(size=8, color=color),
                hovertemplate=(
                    f"<b>{row['نام']}</b><br>"
                    f"سمت: {row['سمت']}<br>"
                    f"شروع: {row['تاریخ شروع']}<br>"
                    f"پایان: {row['تاریخ پایان'] if row['تاریخ پایان'] else 'ادامه دارد'}<br>"
                    "<extra></extra>"
                ),
                showlegend=False
            ),
            row=1, col=1
        )

    # نمودار 2: تایم‌لاین رئیس هیئت مدیره و مدیرعامل
    for idx, row in df.iterrows():
        color = color_map.get(row['سمت'], '#7f7f7f')

        fig.add_trace(
            go.Scatter(
                x=[row['تاریخ_شروع_میلادی'], row['تاریخ_پایان_میلادی']],
                y=[f"{row['نام']} - {row['سمت']}", f"{row['نام']} - {row['سمت']}"],
                mode='lines+markers',
                name=row['سمت'],
                line=dict(color=color, width=8),
                marker=dict(size=10, color=color),
                hovertemplate=(
                    f"<b>{row['نام']}</b><br>"
                    f"سمت: {row['سمت']}<br>"
                    f"شروع: {row['تاریخ شروع']}<br>"
                    f"پایان: {row['تاریخ پایان'] if row['تاریخ پایان'] else 'ادامه دارد'}<br>"
                    "<extra></extra>"
                ),
                showlegend=False
            ),
            row=2, col=1
        )

    # نمودار 3: آمار سمت‌ها
    position_counts = df['سمت'].value_counts()
    fig.add_trace(
        go.Bar(
            x=position_counts.index,
            y=position_counts.values,
            marker_color='#636EFA',
            text=position_counts.values,
            textposition='auto',
            hovertemplate="<b>%{x}</b><br>تعداد: %{y}<extra></extra>",
            showlegend=False
        ),
        row=3, col=1
    )

    # تنظیمات نمایش
    fig.update_xaxes(title_text="زمان", row=1, col=1)
    fig.update_xaxes(title_text="زمان", row=2, col=1)
    fig.update_xaxes(title_text="سمت", tickangle=45, row=3, col=1)

    fig.update_yaxes(title_text="نام عضو", row=1, col=1)
    fig.update_yaxes(title_text="نام و سمت", row=2, col=1)
    fig.update_yaxes(title_text="تعداد", row=3, col=1)

    # تنظیمات کلی
    fig.update_layout(
        title_text="<b>داشبورد تحلیل اعضای شرکت</b>",
        title_font_size=24,
        height=1400,
        showlegend=False,
        hovermode='closest',
        template='plotly_white',
        font=dict(family="Tahoma", size=11)
    )

    # نمایش داشبورد
    fig.show()


# رابط کاربری Streamlit
st.title("🏢 RRK.ir – Company Ads Extractor & Analyzer")

tab1, tab2, tab3 = st.tabs(["🕵️ استخراج اطلاعات شرکت", "📂 بررسی اعضای شرکت", "تایم لاین اعضای شرکت"])

# تب 1: استخراج جدید
with tab1:
    st.markdown("در این بخش می‌توانید با وارد کردن **نام شرکت** یا **شناسه ملی**، آگهی‌های مرتبط را از rrk.ir جمع‌آوری کنید.")
    query = st.text_input("🔍 نام شرکت یا شناسه ملی:")
    start_btn = st.button("شروع استخراج")

    if start_btn:
        if not query.strip():
            st.warning("⚠️ لطفاً نام شرکت یا شناسه ملی را وارد کنید.")
        else:
            with st.spinner("در حال جمع‌آوری آگهی‌ها از rrk.ir ..."):
                ads = scrape_company_ads(query)

            if len(ads) == 0:
                st.error("❌ هیچ آگهی‌ای یافت نشد.")
            else:
                df = pd.DataFrame(ads)
                st.success(f"✅ {len(df)} آگهی یافت شد.")
                st.dataframe(df)

                json_data = json.dumps(ads, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 دانلود JSON",
                    data=json_data,
                    file_name=f"{query}_ads.json",
                    mime="application/json"
                )

                excel_bytes = df.to_excel(index=False, engine="openpyxl")
                st.download_button(
                    "📊 دانلود Excel",
                    data=excel_bytes,
                    file_name=f"{query}_ads.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# تب 2: بارگذاری فایل JSON
with tab2:
    st.markdown("فایل JSON اطلاعات روزنامه رسمی را انتخاب کنید.")
    uploaded = st.file_uploader("📂 فایل JSON را انتخاب کنید", type=["json"], key="file_uploader_1")

    if uploaded is not None:
        try:
            ads = json.load(uploaded)
            st.success(f"✅ فایل با {len(ads)} رکورد بارگذاری شد.")
            st.dataframe(pd.DataFrame(ads))

            # نمایش تحلیل اولیه
            st.markdown("### 📊 تحلیل اولیه")
            st.write("**تعداد شرکت‌ها:**", len(set([ad["نام شرکت"] for ad in ads])))
            st.write("**تعداد آگهی‌ها:**", len(ads))

            llm(ads)
            
        except Exception as e:
            st.error(f"❌ خطا در پردازش اطلاعات شرکت: {e}")

# تب 3: بارگذاری اطلاعات اعضای شرکت
with tab3:
    st.markdown("فایل JSON حاوی اطلاعات اعضای شرکت را انتخاب کنید")
    uploaded2 = st.file_uploader("📂 فایل JSON را انتخاب کنید", type=["json"], key="file_uploader_2")

    if uploaded2 is not None:
        try:
            dataframe = json.load(uploaded2)
            charts(dataframe)
        except Exception as e:
            st.error(f"❌ خطا در نمایش چارت : {e}")



