import streamlit as st
import json
import time
import re
from google import genai
from google.genai import types

# =========================
# ✅ تنظیمات اصلی
# =========================

MODEL_ID = "gemini-2.5-pro"
MAX_RETRIES = 3
BATCH_SIZE = 5
SLEEP_BETWEEN_BATCH = 2

# =========================
# ✅ پرامپت
# =========================

PROMPT_TEXT = """
You are an expert Legal Analyst for Iranian Official Gazette.

For EACH appointment extract:
- person_name
- national_id
- role_raw (exact Persian)
- role_standardized: one of
STANDARD_ROLES = [
    "مدیرعامل",
    "رئیس هیئت مدیره",
    "نایب رئیس هیئت مدیره",
    "عضو هیئت مدیره",
    "عضو هیئت مدیره غیرموظف",
    "قائم مقام مدیرعامل",
    "مدیر اجرایی",
    "مدیر مالی",
    "صاحب امضا",
    "بازرس اصلی",
    "بازرس علی‌البدل",
    "مدیر تصفیه"
]

- start_date (YYYY/MM/DD Persian)
- end_date: (YYYY/MM/DD Persian)
- gazette_no

Return STRICT JSON only:
{
  "results": [
    {
      "company_name": "string",
      "company_id": "string",
      "person_name": "string",
      "Tracking number" : "string",
      "national_id": "string",
      "role_raw": "string",
      "role_standardized": "string",
      "start_date": "string",
      "end_date": "string",
      "gazette_no": "string"
    }
  ]
}

INPUT:
"""

# =========================
# ✅ نرمال‌سازی فارسی و کد ملی
# =========================

def normalize_persian_text(text):
    if not text:
        return ""
    text = str(text)
    replacements = {
        "ي": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "ؤ": "و",
        "إ": "ا",
        "أ": "ا",
        "ء": "",
    }

    for ar, fa in replacements.items():
        text = text.replace(ar, fa)

    text = text.replace("\u200c", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[-–—_]", "", text)
    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


def normalize_national_id(nid):
    if not nid:
        return ""

    nid = normalize_persian_text(nid)
    nid = re.sub(r"\D", "", nid)

    if len(nid) != 10:
        return ""

    if len(set(nid)) == 1:
        return ""

    return nid

# =========================
# ✅ ابزارها
# =========================

def smart_truncate(text, limit=800):
    if not text:
        return ""
    return text[:limit]


def batch_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def extract_json_safe(text):
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        return json.loads(match.group())
    raise ValueError("JSON not found in model output")


def prepare_ads(raw_ads):
    simplified = []

    for ad in raw_ads:
        simplified.append({
            "text": smart_truncate(normalize_persian_text(ad.get("متن آگهی"))),
            "company_name": normalize_persian_text(ad.get("نام شرکت")),
            "company_id": normalize_national_id(ad.get("شناسه ملی شرکت")),
            "gazette_no": normalize_persian_text(ad.get("شماره روزنامه")),
            "date": normalize_persian_text(ad.get("تاریخ روزنامه"))
        })

    return simplified


def merge_duplicate_persons(results):
    merged = {}

    for item in results:
        name_key = normalize_persian_text(item.get("person_name"))
        nid_key = normalize_national_id(item.get("national_id"))

        unique_key = nid_key if nid_key else name_key

        if unique_key not in merged:
            item["person_name"] = name_key
            item["national_id"] = nid_key
            merged[unique_key] = item

    return list(merged.values())


def call_gemini_safe(client, full_prompt):
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=4096
                ),
            )
            return extract_json_safe(response.text)

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = 15 * (attempt + 1)
                st.warning(f"⚠️ محدودیت جمینی! تلاش مجدد تا {wait_time} ثانیه...")
                time.sleep(wait_time)
            else:
                st.error(f"❌ خطای سیستمی: {e}")
                return None

    st.error("❌ سهمیه هوش هنوز آزاد نشده است.")
    return None

# =========================
# ✅ رابط کاربری Streamlit
# =========================

st.set_page_config(page_title="تحلیل روزنامه رسمی هوشمند", layout="centered")

st.title("📄 تحلیل هوشمند آگهی‌های روزنامه رسمی")
st.write("آپلود فایل ورودی JSON → تحلیل هوشمند → دانلود خروجی")

api_key = st.text_input("🔑 Key را وارد کنید:", type="password")

uploaded_file = st.file_uploader("📤 فایل ورودی JSON آگهی‌ها را آپلود کنید:", type=["json"])

if uploaded_file and api_key:

    try:
        raw_ads = json.load(uploaded_file)
        st.success(f"✅ فایل با موفقیت بارگذاری شد | تعداد آگهی‌ها: {len(raw_ads)}")
    except Exception:
        st.error("❌ فایل JSON معتبر نیست")
        st.stop()

    if st.button("🚀 شروع تحلیل با هوش مصنوعی"):

        client = genai.Client(api_key=api_key)
        simplified_ads = prepare_ads(raw_ads)

        all_results = []
        progress = st.progress(0)
        total_batches = (len(simplified_ads) // BATCH_SIZE) + 1

        batch_counter = 0

        for batch in batch_list(simplified_ads, BATCH_SIZE):

            batch_counter += 1
            st.write(f"🔄 در حال پردازش Batch {batch_counter} از {total_batches}")

            full_prompt = PROMPT_TEXT + json.dumps(
                batch, ensure_ascii=False, separators=(",", ":")
            )

            data = call_gemini_safe(client, full_prompt)

            if data and "results" in data:
                all_results.extend(data["results"])

            progress.progress(batch_counter / total_batches)
            time.sleep(SLEEP_BETWEEN_BATCH)

        final_output = {
            "results": merge_duplicate_persons(all_results)
        }

        st.success("✅ تحلیل کامل شد!")

        st.download_button(
            label="⬇️ دانلود فایل خروجی JSON",
            data=json.dumps(final_output, ensure_ascii=False, indent=2),
            file_name="output_analyzed.json",
            mime="application/json"
        )

else:
    st.warning("⚠️ لطفاً API Key و فایل ورودی را وارد کنید.")
