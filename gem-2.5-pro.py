import json
import time
import streamlit as st
from google import genai
from google.genai import types


def analyze_ads_with_gemini(api_key, model_id, ads_list):
    client = genai.Client(api_key=api_key)

    # --- SYSTEM PROMPT ---
    prompt_text = """
You are an expert Legal Analyst for Iranian Official Gazette (Roznameh Rasmi).

Your Task: Analyze the list of company advertisement texts provided in JSON format.

Extract the following information for each appointed individual or entity:
1. person_name
2. national_id
3. role_raw (EXACT Persian text)
4. role_standardized (One of: ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره", "عضو هیئت مدیره", "مدیرعامل و عضو هیئت مدیره", "بازرس اصلی", "بازرس علی‌البدل"])
5. start_date (YYYY/MM/DD Persian)
6. end_date (If 2 years → +2 years, If 1 year → +1 year)
7. gazette_no

STRICT JSON OUTPUT ONLY. No explanation.

Schema:
{
  "results": [
    {
      "company_name": "string",
      "company_id": "string",
      "person_name": "string",
      "national_id": "string",
      "role_raw": "string",
      "role_standardized": "string",
      "start_date": "string",
      "end_date": "string",
      "gazette_no": "string"
    }
  ]
}
"""

    # --- TOKEN OPTIMIZATION ---
    simplified_ads = [
        {
            "text": ad.get("متن آگهی"),
            "date": ad.get("تاریخ روزنامه"),
            "number": ad.get("شماره روزنامه"),
            "company_id": ad.get("شناسه ملی شرکت"),
            "company_name": ad.get("نام شرکت")
        }
        for ad in ads_list
    ]

    full_prompt = prompt_text + "\nINPUT DATA:\n" + json.dumps(
        simplified_ads, ensure_ascii=False, separators=(",", ":")
    )

    # --- RETRY SAFE GUARD FOR 429 ---
    MAX_RETRIES = 3

    for attempt in range(MAX_RETRIES):
        try:
            with st.spinner("در حال تحلیل با Gemini 2.5 Pro ..."):
                response = client.models.generate_content(
                    model=model_id,  # ✅ gemini-2.5-pro
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=4096
                    ),
                )

                return json.loads(response.text)

        except Exception as e:
            if "429" in str(e):
                wait_time = 15 * (attempt + 1)
                st.warning(f"محدودیت Gemini! تلاش مجدد تا {wait_time} ثانیه...")
                time.sleep(wait_time)
            else:
                st.error(f"خطای غیرمنتظره: {e}")
                return None

    st.error("❌ پس از چند تلاش، محدودیت Gemini برطرف نشد.")
    return None
