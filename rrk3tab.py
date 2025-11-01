import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, logging, os, pandas as pd

st.set_page_config(page_title="استخراج آگهی‌های rrk.ir", layout="wide")
st.title("📰 استخراج آگهی‌های شرکت از rrk.ir")

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


# -----------------------------
# رابط کاربری Streamlit
# -----------------------------
query = st.text_input("🔍 نام شرکت یا شناسه ملی را وارد کنید:")

if st.button("جستجو و استخراج آگهی‌ها"):
    with st.spinner("در حال جستجو در rrk.ir ..."):
        data, shot = scrape_company_ads(query)

    st.image(shot, caption="نمایی از صفحه rrk.ir", use_container_width=True)

    if not data:
        st.error("❌ هیچ آگهی‌ای یافت نشد.")
    else:
        df = pd.DataFrame(data)
        st.dataframe(df)
        st.download_button(
            "📥 دانلود فایل Excel",
            df.to_excel(index=False, engine='openpyxl'),
            file_name=f"ads_{query}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
