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
import undetected_chromedriver as uc


# -----------------------------
# تنظیمات Chrome
# -----------------------------
def setup_driver(headless=True):
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--lang=fa-IR")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/118.0.5993.70 Safari/537.36")
    if headless:
        chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    driver.implicitly_wait(10)
    wait = WebDriverWait(driver, 60)
    return driver, wait

# -----------------------------
# ابزارهای ذخیره برای دیباگ
# -----------------------------
def save_debug(driver, name):
    """ذخیره اسکرین‌شات و HTML در پوشه debug"""
    os.makedirs("debug", exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"debug/{timestamp}_{name}"
    try:
        driver.save_screenshot(f"{base}.png")
        with open(f"{base}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"📸 Debug saved: {base}")
    except Exception as e:
        logging.warning(f"⚠️ خطا در ذخیره debug: {e}")

# -----------------------------
# توابع کمکی
# -----------------------------
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

# -----------------------------
# تابع اصلی
# -----------------------------
def scrape_company_ads(query, headless=True):
    driver, wait = setup_driver(headless=headless)
    ad_data = []

    try:
        logging.info("🚀 شروع جستجو در rrk.ir ...")
        driver.get("https://www.rrk.ir/")
        time.sleep(2)
        save_debug(driver, "home")

        search_box = wait.until(EC.presence_of_element_located((By.ID, "P0_SEARCH_ITEM")))
        search_box.clear()
        search_box.send_keys(query)
        driver.find_element(By.ID, "BTN_ADVANCEDSEARCH").click()

        time.sleep(3)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "t-LinksList-link"))).click()
        time.sleep(3)
        save_debug(driver, "results_page")

        current_page = 1
        while True:
            ad_links = get_links(driver)
            if not ad_links:
                logging.info("🚫 آگهی جدیدی یافت نشد.")
                save_debug(driver, f"no_ads_page_{current_page}")
                break

            for tag in ad_links:
                href = tag.get("href")
                if not href.startswith("/ords/r/rrs/rrs-front/f-detail-ad"):
                    continue
                url = "https://rrk.ir" + href

                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(url)

                try:
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    data = extract_fields(driver, soup)
                    data["url"] = url
                    ad_data.append(data)
                    logging.info(f"✅ آگهی استخراج شد: {url}")
                except Exception as e:
                    logging.warning(f"⚠️ خطا در استخراج آگهی: {e}")
                    save_debug(driver, "ad_error")
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1.5)

            next_buttons = driver.find_elements(By.CSS_SELECTOR, "ul.a-GV-pageSelector-list li button.a-GV-pageButton")
            next_btn = next((b for b in next_buttons if b.text.isdigit() and int(b.text) == current_page + 1), None)
            if not next_btn:
                logging.info("📄 صفحه بعدی یافت نشد.")
                break
            driver.execute_script("arguments[0].click();", next_btn)
            current_page += 1
            time.sleep(5)

    except Exception as e:
        logging.error(f"❌ خطا کلی: {e}")
        save_debug(driver, "fatal_error")
    finally:
        driver.quit()

    return ad_data

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
        model_name="gemini-1.5-pro",  # تصحیح مدل به نسخه معتبر
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
    if not data or ('اعضای سابق شرکت' not in data and 'اعضای فعلی شرکت' not in data):
        st.error("❌ داده‌ها معتبر نیستند. لطفاً JSON معتبر حاوی 'اعضای سابق شرکت' یا 'اعضای فعلی شرکت' آپلود کنید.")
        return
    
    # ترکیب اعضای فعلی و سابق
    all_members = []
    if 'اعضای فعلی شرکت' in data:
        all_members.extend(data['اعضای فعلی شرکت'])
    if 'اعضای سابق شرکت' in data:
        all_members.extend(data['اعضای سابق شرکت'])
    
    if not all_members:
        st.warning("⚠️ هیچ عضوی یافت نشد.")
        return
    
    # تبدیل داده‌ها به DataFrame
    df = pd.DataFrame(all_members)
    
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
    key_positions = df[df['سمت'].str.contains('مدیرعامل|رئیس هیئت|رئیس هیات', na=False)]
    for idx, row in key_positions.iterrows():
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

    # نمایش داشبورد در Streamlit
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------------
# رابط کاربری Streamlit
# ----------------------------------
st.title("🏢 RRK.ir – استخراج اطلاعات روزنامه رسمی به همراه اطلاع رسانی اعضا و تایم لاین")

tab1, tab2, tab3 = st.tabs(["🕵️ استخراج اطلاعات شرکت", "📂 بررسی اعضای شرکت", "تایم لاین اعضای شرکت"])

# --------------------------
# تب 1: استخراج جدید
# --------------------------
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

# --------------------------
# تب 2: بارگذاری فایل JSON
# --------------------------
with tab2:
    st.markdown("در این بخش می‌توانید فایل JSON ذخیره‌شده را بارگذاری و تحلیل کنید.")
    uploaded = st.file_uploader("📂 فایل JSON را انتخاب کنید", type=["json"])

    if uploaded is not None:
        try:
            ads = json.load(uploaded)
            df = pd.DataFrame(ads)
            st.success(f"✅ فایل با {len(df)} رکورد بارگذاری شد.")
            st.dataframe(df)

            # نمایش تحلیل اولیه
            st.markdown("### 📊 تحلیل اولیه")
            st.write("**تعداد شرکت‌ها:**", df["نام شرکت"].nunique())
            st.write("**تعداد آگهی‌ها:**", len(df))
            st.write("**بازه زمانی:**", f"{df['تاریخ نامه'].min()} تا {df['تاریخ نامه'].max()}")

            # پردازش با LLM و نمایش خروجی
            with st.spinner("در حال تحلیل با هوش مصنوعی..."):
                analyzed_data = llm(ads)
            
            st.markdown("### 🤖 تحلیل اعضای شرکت")
            st.json(analyzed_data)
            
            # دانلود فایل خروجی
            with open("company_members.json", "r", encoding="utf-8") as f:
                json_content = f.read()
            st.download_button(
                "📥 دانلود JSON تحلیل‌شده",
                data=json_content,
                file_name="company_members.json",
                mime="application/json"
            )
            
            # فیلتر بر اساس شرکت یا تاریخ
            company_filter = st.selectbox("🏢 انتخاب شرکت", df["نام شرکت"].unique())
            df_filtered = df[df["نام شرکت"] == company_filter]
            st.dataframe(df_filtered)


            # دکمه دانلود مجدد
            st.download_button(
                "📤 دانلود فیلترشده (Excel)",
                data=df_filtered.to_csv(index=False).encode("utf-8"),
                file_name=f"{company_filter}_filtered.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"❌ خطا در خواندن فایل: {e}")

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

            # پردازش با LLM و نمایش خروجی
            with st.spinner("در حال تحلیل با هوش مصنوعی..."):
                analyzed_data = llm(ads)
            
            st.markdown("### 🤖 تحلیل اعضای شرکت")
            st.json(analyzed_data)
            
            # دانلود فایل خروجی
            with open("company_members.json", "r", encoding="utf-8") as f:
                json_content = f.read()
            st.download_button(
                "📥 دانلود JSON تحلیل‌شده",
                data=json_content,
                file_name="company_members.json",
                mime="application/json"
            )
            
        except Exception as e:
            st.error(f"❌ خطا در پردازش اطلاعات شرکت: {e}")

# تب 3: بارگذاری اطلاعات اعضای شرکت
with tab3:
    st.markdown("فایل JSON حاوی اطلاعات اعضای شرکت را انتخاب کنید")
    uploaded2 = st.file_uploader("📂 فایل JSON را انتخاب کنید", type=["json"], key="file_uploader_2")

    if uploaded2 is not None:
        try:
            dataframe = json.load(uploaded2)
            st.success("✅ فایل بارگذاری شد. در حال نمایش داشبورد...")
            charts(dataframe)
        except Exception as e:
            st.error(f"❌ خطا در نمایش چارت: {e}")

tab1, tab2, tab3 = st.tabs(["🕵️ استخراج اطلاعات شرکت", "📂 بررسی اعضای شرکت", "تایم لاین اعضای شرکت"])
