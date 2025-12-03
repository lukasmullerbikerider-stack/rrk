import streamlit as st
import json
import google.generativeai as genai
import os

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="تحلیل روزنامه رسمی با هوش مصنوعی", layout="wide")

# بهتر است کلید را از متغیر محیطی بخوانی، نه داخل کد
API_KEY = os.getenv("GENAI_API_KEY", "AIzaSyAA90H731pSoYBT7q3yrHEUmM5bwP7wtQs")  # ← جایگزین کن یا بهتر: export GENAI_API_KEY=...
genai.configure(api_key=API_KEY)

# از gemini-3 استفاده می‌کنیم
MODEL = "gemini-3"

# -----------------------------
# SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = """
You are an advanced information extraction engine specialized in Iranian Official Gazette (روزنامه رسمی).  
The input will be a JSON object where each key is a newspaper issue like "23335 تهران" and value is an array of extracted people.

Your task:
1. For each newspaper (each key in the input JSON), convert all person entries to ROLE MAPPING structured JSON.
2. Normalize roles using the ROLE MAPPING LIST below.
3. Keep output grouped by newspaper key (do NOT merge newspapers).
4. Fix incomplete or wrong roles and map Persian roles to standard roles.
5. Convert dates to YYYY-MM-DD.
6. Extract announcement_id from the key (e.g. "23335 تهران" → announcement_id = "23335 تهران").

------------------------------------
ROLE MAPPING EXAMPLES
- "رئیس هیئت مدیره" → BoardChair
- "نایب رئیس هیئت مدیره" → BoardViceChair
- "عضو هیئت مدیره" → BoardMember
- "عضو اصلی" → BoardMemberPrincipal
- "عضو علی‌البدل" → BoardMemberAlternate
- "مدیرعامل" → CEO
- "مدیر شعبه" → BranchManager
- "بازرس اصلی" → Auditor
- "بازرس علی‌البدل" → AuditorAlternate
- "دارنده حق امضا" → AuthorizedSignatory

If the role is unclear or garbage → ignore that item.

------------------------------------
OUTPUT FORMAT:
Return ONLY this final JSON format:

{
  "23335 تهران": [
    {
      "announcement_id": "23335 تهران",
      "full_name": "string",
      "national_id": "string|null",
      "role": "standard_role",
      "original_role_text": "string",
      "start_date": "YYYY-MM-DD|null",
      "end_date": "YYYY-MM-DD|null"
    }
  ]
}

RULES:
- One object per person-role.
- Keep Persian names as-is.
- Must return VALID JSON.
"""

# -----------------------------
# UI
# -----------------------------
st.title("🔍 تحلیل هوش مصنوعی روزنامه رسمی – Streamlit + Gemini")
st.write("یک JSON ورودی بده، روی دکمه تحلیل کلیک کن، خروجی ساختاریافته تحویل بگیر.")

uploaded_file = st.file_uploader("فایل JSON ورودی را انتخاب کنید", type=["json"])
manual_input = st.text_area("یا JSON را اینجا وارد کنید", height=300)

# -----------------------------
# PROCESS BUTTON
# -----------------------------
if st.button("🚀 تحلیل هوش مصنوعی"):
    if uploaded_file:
        input_json = json.loads(uploaded_file.read())
    else:
        try:
            input_json = json.loads(manual_input)
        except:
            st.error("ورودی JSON معتبر نیست.")
            st.stop()

    # مدل Gemini 3 — با 'thinking_level' روی "high" برای تفکر عمیق تر
    model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)

    with st.spinner("در حال تحلیل داده‌ها..."):
        # پارامترهای مهم:
        # - thinking_level="high" -> از بودجهٔ تفکرِ بیشتر Gemini 3 استفاده می‌کند (THINK HIGH).
        # - temperature پایین‌تر باعث ثبات و قاطعیت خروجی می‌شود؛ در صورت نیاز می‌توانی آن را بالا ببری.
        # - max_output_tokens را متناسب با میزان خروجی JSON تنظیم کن.
        response = model.generate_content(
            json.dumps(input_json),
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=4096,
            candidate_count=1
        )

    try:
        ai_output = json.loads(response.text)
    except Exception:
        st.error("خروجی مدل JSON معتبر نیست. متن خروجی:")
        st.code(response.text)
        st.stop()

    st.success("پردازش کامل شد!")
    st.json(ai_output)

    # دانلود خروجی
    st.download_button(
        label="📥 دانلود خروجی JSON",
        data=json.dumps(ai_output, ensure_ascii=False, indent=2),
        file_name="ai_processed.json",
        mime="application/json"
    )
