
import streamlit as st
import json
import time
import re
from google import genai
from google.genai import types

# ==================================================
# 🔧 CONFIG (Production)
# ==================================================

MODEL_ID = "gemini-2.5-pro"
MAX_RETRIES = 3
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE = 0.1

# ==================================================
# 🧠 PROMPT (Strict – JSON Only)
# ==================================================

PROMPT_TEXT = """
You are an expert Legal Analyst for Iranian Official Gazette.

CRITICAL RULES:
- Return VALID JSON only
- No explanation
- No markdown
- No extra text

From EACH appointment extract:
- company_name
- company_id
- person_name
- national_id
- role_raw (exact Persian)
- role_standardized (one of the allowed roles)
- start_date (YYYY/MM/DD Persian)
- end_date (YYYY/MM/DD Persian)
- gazette_no
- tracking_number (شماره پیگیری / کد پیگیری)
- letter_number (شماره نامه)

Allowed role_standardized values:
[
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

If a value does not exist, return empty string "".

Return STRICT JSON only:
{
  "results": [
    {
      "company_name": "string",
      "company_id": "string",
      "person_name": "string",
      "national_id": "string",
      "tracking_number": "string",
      "letter_number": "string",
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

# ==================================================
# 🔤 NORMALIZATION
# ==================================================

def normalize_persian_text(text: str) -> str:
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
    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


def normalize_national_id(nid: str) -> str:
    if not nid:
        return ""

    nid = normalize_persian_text(nid)
    nid = re.sub(r"\D", "", nid)

    if len(nid) != 10 or len(set(nid)) == 1:
        return ""

    return nid

# ==================================================
# 🛠 DATA PREPARATION
# ==================================================

def prepare_ads(raw_ads: list) -> list:
    prepared = []

    for ad in raw_ads:
        prepared.append({
            "text": normalize_persian_text(ad.get("متن آگهی")),
            "company_name": normalize_persian_text(ad.get("نام شرکت")),
            "company_id": normalize_national_id(ad.get("شناسه ملی شرکت")),
            "gazette_no": normalize_persian_text(ad.get("شماره روزنامه")),
            "date": normalize_persian_text(ad.get("تاریخ روزنامه")),
        })

    return prepared


def merge_duplicate_persons(results: list) -> list:
    merged = {}

    for item in results:
        name_key = normalize_persian_text(item.get("person_name"))
        nid_key = normalize_national_id(item.get("national_id"))

        unique_key = nid_key or name_key

        if unique_key and unique_key not in merged:
            item["person_name"] = name_key
            item["national_id"] = nid_key
            merged[unique_key] = item

    return list(merged.values())

# ==================================================
# 🤖 GEMINI CALL (Single Call)
# ==================================================

def extract_json_safe(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("No JSON found in model output")
    return json.loads(match.group())


def call_gemini_once(client, full_prompt: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=TEMPERATURE,
					thinking_config=types.ThinkingConfig(thinking_level="low")
                ),
            )
            return extract_json_safe(response.text)

        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                wait = attempt * 10
                st.warning(f"⏳ محدودیت Gemini – تلاش مجدد بعد از {wait} ثانیه")
                time.sleep(wait)
            else:
                st.error(f"❌ خطای غیرمنتظره: {e}")
                return None

    return None

# ==================================================
# 🖥 STREAMLIT UI
# ==================================================

st.set_page_config("تحلیل Production-Ready روزنامه رسمی", layout="centered")
st.title("📄 تحلیل هوشمند آگهی‌های روزنامه رسمی (Production)")

api_key = st.text_input("🔑 Gemini API Key", type="password")
uploaded_file = st.file_uploader("📤 فایل JSON آگهی‌ها", type=["json"])

if api_key and uploaded_file:

    try:
        raw_ads = json.load(uploaded_file)
        st.success(f"✅ فایل بارگذاری شد | تعداد آگهی‌ها: {len(raw_ads)}")
    except Exception:
        st.error("❌ فایل JSON نامعتبر است")
        st.stop()

    if st.button("🚀 اجرای تحلیل (Single Call)"):

        client = genai.Client(api_key=api_key, http_options={"base_url": "https://api.avalai.ir"})

        prepared_ads = prepare_ads(raw_ads)

        full_prompt = PROMPT_TEXT + json.dumps(
            prepared_ads, ensure_ascii=False, separators=(",", ":")
        )

        st.info("🧠 ارسال داده‌ها به Gemini 2.5 Pro ...")

        result = call_gemini_once(client, full_prompt)

        if not result or "results" not in result:
            st.error("❌ خروجی معتبر دریافت نشد")
            st.stop()

        final_output = {
            "results": merge_duplicate_persons(result["results"])
        }

        st.success("✅ تحلیل با موفقیت انجام شد")

        st.download_button(
            "⬇️ دانلود خروجی JSON",
            json.dumps(final_output, ensure_ascii=False, indent=2),
            file_name="output_production.json",
            mime="application/json"
        )

else:
    st.warning("⚠️ لطفاً API Key و فایل JSON را وارد کنید")
