import zipfile
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def create_proxy_extension(proxy_host, proxy_port, proxy_user, proxy_pass):
    """ایجاد افزونه‌ی proxy با یوزر و پسورد"""
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
        },
        "minimum_chrome_version":"22.0.0"
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

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{proxy_user}",
                password: "{proxy_pass}"
            }}
        }};
    }}
    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    pluginfile = "proxy_auth_plugin.zip"

    with zipfile.ZipFile(pluginfile, "w") as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)

    return pluginfile

def setup_driver():
    proxy_host = "85.185.120.203"
    proxy_port = 42073
    proxy_user = "7h8o8te9k6"
    proxy_pass = "LuDCEq3Rv7"

    pluginfile = create_proxy_extension(proxy_host, proxy_port, proxy_user, proxy_pass)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_extension(pluginfile)

    driver = webdriver.Chrome(options=chrome_options)
    return driver

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

driver = setup_driver()
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
