import streamlit as st
import json
import google.generativeai as genai
import os

# ----------------------------------
# CONFIG
# ----------------------------------
st.set_page_config(page_title="تحلیل نقش افراد در روزنامه رسمی – Gemini 3.0", layout="wide")

API_KEY = os.getenv("GENAI_API_KEY", "AIzaSyAA90H731pSoYBT7q3yrHEUmM5bwP7wtQs")
genai.configure(api_key=API_KEY)

MODEL = "gemini-3"

# ----------------------------------
# SYSTEM PROMPT
# ----------------------------------
SYSTEM_PROMPT = """
You are an expert information-extraction engine for Iranian Official Gazette data.

The user will send JSON like:
{
  "23257 تهران": [
    {
      "نام": "...",
      "کد ملی": "...",
      "سمت": "...",
      "تاریخ شروع": "...",
      "تاریخ پایان": null
    }
  ]
}

Your job is to produce a **role history** for each person with:
- standardized official role (canonical role)
- original extracted role text
- computed end date based on newer announcements

----------------------------------------------------------
ROLE MAPPING → official_role
----------------------------------------------------------
Map Persian roles to canonical English roles:

- رئیس هیئت مدیره → BoardChair
- نایب رئیس هیئت مدیره → BoardViceChair
- عضو هیئت مدیره → BoardMember
- عضو اصلی → BoardMemberPrincipal
- عضو علی‌البدل → BoardMemberAlternate
- مدیرعامل → CEO
- مدیر شعبه → BranchManager
- بازرس اصلی → Auditor
- بازرس علی‌البدل → AuditorAlternate
- دارنده حق امضا → AuthorizedSignatory

If none applies → official_role = null

----------------------------------------------------------
DATE RULES
----------------------------------------------------------
Convert:
- 1403/10/10
- 31/04/1403
- 03/08/1401

Into:
YYYY-MM-DD

If impossible → null.

----------------------------------------------------------
END DATE COMPUTATION
----------------------------------------------------------
For each person:

end_date = the start_date of the next announcement where the same person appears.

If no later announcement exists → end_date = null.

----------------------------------------------------------
OUTPUT FORMAT (STRICT JSON)
----------------------------------------------------------
{
  "23257 تهران": [
    {
      "announcement_id": "23257 تهران",
      "full_name": "string",
      "national_id": "string|null",
      "official_role": "string|null",
      "extracted_role_text": "string",
      "start_date": "YYYY-MM-DD|null",
      "end_date": "YYYY-MM-DD|null"
    }
  ]
}

RULES
------
- Keep announcements separate.
- One record per person per role.
- Names stay exactly as written in Persian.
- official_role mapped & extracted_role_text preserved.
- end_date computed based on next announcement.
- Output ONLY valid JSON.
"""

# ----------------------------------
# UI
# ----------------------------------
st.title("🧠 استخراج و زمان‌بندی نقش افراد – Gemini 3.0")
st.write("JSON روزنامه رسمی را بدهید. خروجی شامل سمت رسمی + سمت استخراج‌شده + تاریخ شروع + پایان خواهد بود.")

uploaded_file = st.file_uploader("فایل JSON را بارگذاری کنید", type=["json"])
manual_input = st.text_area("یا JSON را اینجا وارد کنید", height=300)

if st.button("🚀 پردازش با Gemini 3.0"):
    
    if uploaded_file:
        input_json = json.loads(uploaded_file.read())
    else:
        try:
            input_json = json.loads(manual_input)
        except:
            st.error("❌ JSON معتبر نیست.")
            st.stop()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT
    )

    with st.spinner("در حال پردازش ..."):
      response = model.generate_content(
          json.dumps(input_json, ensure_ascii=False),
          temperature=0.1,          # مدل را پایدار و دقیق نگه می‌دارد
          top_p=0.95,
          candidate_count=1,
          max_output_tokens=4096    # برای خروجی JSON طولانی
      )


    try:
        final_data = json.loads(response.text)
    except:
        st.error("خروجی JSON معتبر نیست:")
        st.code(response.text)
        st.stop()

    st.success("🎉 آماده است")
    st.json(final_data)

    st.download_button(
        "📥 دانلود خروجی",
        data=json.dumps(final_data, ensure_ascii=False, indent=2),
        file_name="role_history.json",
        mime="application/json"
    )
