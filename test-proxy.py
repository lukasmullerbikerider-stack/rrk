import zipfile
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import streamlit as st

# -----------------------------
# Proxy Extension Creator
# -----------------------------
def create_proxy_extension(proxy_host, proxy_port, proxy_user, proxy_pass):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy_host}",
                port: parseInt({proxy_port})
            }},
            bypassList: ["localhost"]
        }}
    }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    chrome.webRequest.onAuthRequired.addListener(
        function(details) {{
            return {{
                authCredentials: {{
                    username: "{proxy_user}",
                    password: "{proxy_pass}"
                }}
            }};
        }},
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    pluginfile = "proxy_auth_plugin.zip"
    with zipfile.ZipFile(pluginfile, "w") as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)

    return pluginfile

# -----------------------------
# Driver setup
# -----------------------------
def setup_driver(proxy_host, proxy_port, proxy_user, proxy_pass):
    pluginfile = create_proxy_extension(proxy_host, proxy_port, proxy_user, proxy_pass)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_extension(pluginfile)

    return webdriver.Chrome(options=chrome_options)

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🌐 تست پروکسی با Selenium روی RRK.ir")

proxy_user = "7h8o8te9k6"
proxy_pass = "LuDCEq3Rv7"
proxy_host = "85.185.120.203"
proxy_port = "42073"

start_btn = st.button("🚀 شروع تست پروکسی")

if start_btn:
    if not proxy_host or not proxy_port or not proxy_user or not proxy_pass:
        st.error("⚠️ لطفاً تمام فیلدها را پر کنید.")
    else:
        try:
            st.info("⏳ در حال اتصال از طریق پروکسی …")
            driver = setup_driver(proxy_host, proxy_port, proxy_user, proxy_pass)
            driver.get("https://www.rrk.ir/")
            time.sleep(3)

            # Verify page loaded
            page_title = driver.title
            st.success(f"✅ متصل شد! عنوان صفحه: {page_title}")

            # Full page screenshot
            width = 1366
            height = driver.execute_script(
                "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
            )
            driver.set_window_size(width, height)
            time.sleep(1)

            filename = "rrk_fullpage.png"
            driver.save_screenshot(filename)

            with open(filename, "rb") as f:
                img_bytes = f.read()

            st.image(img_bytes, caption="📸 اسکرین‌شات تمام صفحه")
            st.download_button("دانلود تصویر", img_bytes, file_name=filename, mime="image/png")

        except Exception as e:
            st.error(f"❌ خطا در تست پروکسی: {e}")
        finally:
            try:
                driver.quit()
            except:
                pass
