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
import jdatetime
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -----------------------------
# تنظیم مرورگر سازگار با Posit
# -----------------------------
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # حالت جدید headless
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--proxy-server=http://85.185.120.203:42073")
    
    chrome_path = "/usr/bin/google-chrome"
    if os.path.exists(chrome_path):
        chrome_options.binary_location = chrome_path

    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    wait = WebDriverWait(driver, 60)
    return driver, wait


# -----------------------------
# توابع استخراج
# -----------------------------
def get_links(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    return soup.select("a[href*='/ords/r/rrs/rrs-front/f-detail-ad']")

def extract_fields(driver, soup):
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


def scrape_company_ads(query):
    driver, wait = setup_driver()
    ad_data = []
    screenshot_path = "/tmp/rrk.png"

    try:
        driver.get("https://www.rrk.ir/")
        driver.save_screenshot(screenshot_path)

        search_box = wait.until(EC.presence_of_element_located((By.ID, "P0_SEARCH_ITEM")))
        search_box.clear()
        search_box.send_keys(query)
        driver.find_element(By.ID, "BTN_ADVANCEDSEARCH").click()
        time.sleep(3)

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
                time.sleep(2)
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

    return ad_data, screenshot_path


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
        model_name="gemini-2.5-pro",  # تصحیح مدل به نسخه معتبر
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
    df = pd.DataFrame(data)

    st.markdown("### 📊 داشبورد اعضای شرکت")
    st.write("در این بخش وضعیت اعضای شرکت و مدیران را مشاهده می‌کنید.")

    st.divider()

    # ---------------------- نمودار اول: همه اعضا -----------------------
    st.markdown("#### 👥 نمودار تعداد اعضای شرکت بر اساس سال")

    colA1, colA2 = st.columns(2)

    with colA1:
        st.write("📅 انتخاب ستون تاریخ:")
        date_col1 = st.selectbox("ستون تاریخ اعضا را انتخاب کنید:", df.columns, key="date1")

    with colA2:
        st.write("📛 ستون نام افراد:")
        name_col1 = st.selectbox("ستون نام افراد را انتخاب کنید:", df.columns, key="name1")

    df_members = df.groupby(df[date_col1])[name_col1].count().reset_index()
    df_members.columns = ["date", "count"]

    fig_members = px.line(df_members, x="date", y="count", markers=True, title="روند تغییرات اعضا شرکت")
    fig_members.update_layout(legend_title_text="نوع", xaxis_title="تاریخ", yaxis_title="تعداد", legend=dict(x=0.01, y=0.99))

    st.plotly_chart(fig_members, use_container_width=True)

    st.download_button(
        "📥 دانلود داده اعضا (CSV)",
        df_members.to_csv(index=False).encode("utf-8"),
        "members_chart_data.csv",
        "text/csv"
    )

    st.divider()

    # ------------------ نمودار دوم: مدیرعامل + هیئت مدیره --------------------
    st.markdown("#### 👔 نمودار تغییرات مدیرعامل و هیئت مدیره")

    colB1, colB2, colB3 = st.columns(3)

    with colB1:
        date_col2 = st.selectbox("📅 ستون تاریخ:", df.columns, key="date2")

    with colB2:
        role_col = st.selectbox("🎭 ستون سمت/نقش:", df.columns, key="role2")

    with colB3:
        st.write("🔎 انتخاب نقش‌ها")
        roles_selected = st.multiselect("نقش‌هایی که می‌خوای نمایش داده بشه:", df[role_col].unique(), default=df[role_col].unique())

    df_role = df[df[role_col].isin(roles_selected)]

    df_role_count = df_role.groupby([df_role[date_col2], df_role[role_col]]).size().reset_index(name="count")
    df_role_count.columns = ["date", "role", "count"]

    fig_roles = px.line(df_role_count, x="date", y="count", color="role", markers=True,
                       title="روند تغییرات مدیرعامل و اعضای هیئت مدیره")

    fig_roles.update_layout(legend_title_text="سمت", xaxis_title="تاریخ", yaxis_title="تعداد",
                            legend=dict(x=0.01, y=0.99))

    st.plotly_chart(fig_roles, use_container_width=True)

    st.download_button(
        "📥 دانلود داده مدیران (CSV)",
        df_role_count.to_csv(index=False).encode("utf-8"),
        "board_chart_data.csv",
        "text/csv"
    )

# -------------- تنظیمات صفحه و RTL --------------
st.set_page_config(page_title="تحلیل آگهی و اعضای شرکت", page_icon="📊", layout="wide")

st.markdown("""
<style>
body { direction: rtl; text-align: right; }
div[data-testid="stVerticalBlock"] > div { direction: rtl; }
.css-1kyxreq { direction: rtl; }
.block-container { direction: rtl; text-align: right; }
</style>
""", unsafe_allow_html=True)

# عنوان صفحه
st.markdown("<h2 style='text-align:center;'>📂 سامانه تحلیل آگهی و اعضای شرکت</h2>", unsafe_allow_html=True)

# --------------------------
# رابط کاربری Streamlit
# --------------------------
st.title("🏢 RRK.ir – استخراج اطلاعات روزنامه رسمی و تحلیل اعضا")

tab1, tab2 = st.tabs(["🕵️ استخراج اطلاعات شرکت", "📂 تحلیل و داشبورد اعضای شرکت"])

# --------------------------
# ✅ تب 1: استخراج جدید
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

                # دانلود JSON و Excel
                json_data = json.dumps(ads, ensure_ascii=False, indent=2)
                st.download_button("📥 دانلود JSON", json_data, f"{query}_ads.json", "application/json")

                excel_bytes = df.to_excel(index=False, engine="openpyxl")
                st.download_button("📊 دانلود Excel", excel_bytes, f"{query}_ads.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --------------------------
# ✅ تب 2: بارگذاری + LLM + داشبورد
# --------------------------
with tab2:
    st.markdown("در این بخش فایل JSON خروجی را بارگذاری کنید تا اطلاعات اعضا استخراج و نمودار ترسیم شود.")
    
    uploaded = st.file_uploader("📂 فایل JSON آگهی شرکت را انتخاب کنید", type=["json"])

    if uploaded is not None:
        try:
            ads = json.load(uploaded)
            df = pd.DataFrame(ads)
            st.success(f"✅ فایل با {len(df)} رکورد بارگذاری شد.")

            st.dataframe(df)

            st.markdown("### 🧠 پردازش با هوش مصنوعی (استخراج اعضای شرکت)")

            with st.spinner("در حال تحلیل با LLM ..."):
                analyzed_data = llm(ads)  # ✅ خروجی مستقیم برای چارت‌ها

            st.success("✅ تحلیل اعضای شرکت انجام شد")

            # نمایش JSON خروجی
            with st.expander("📄 مشاهده اطلاعات استخراج‌شده اعضا"):
                st.json(analyzed_data)

            st.download_button(
                "📥 دانلود JSON تحلیل‌شده",
                data=json.dumps(analyzed_data, ensure_ascii=False, indent=2),
                file_name="company_members.json",
                mime="application/json"
            )

            st.markdown("### 📈 داشبورد اعضای شرکت")
            charts(analyzed_data)  # ✅ نمودار مستقیم بعد از LLM

        except Exception as e:
            st.error(f"❌ خطا: {e}")
