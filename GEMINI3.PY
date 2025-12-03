import streamlit as st
import json
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import jdatetime

# --- Page Config ---
st.set_page_config(page_title="تحلیلگر روزنامه رسمی با جمینی", layout="wide")

st.title("📊 تحلیل هوشمند آگهی‌های روزنامه رسمی (نسخه دقیق)")
st.markdown("استخراج سمت دقیق و استاندارد، تاریخ‌ها و رسم تایم‌لاین مدیریتی")

# --- Sidebar ---
st.sidebar.header("تنظیمات")
api_key = st.sidebar.text_input("Gemini API Key", type="password")
uploaded_file = st.sidebar.file_uploader("آپلود فایل JSON روزنامه رسمی", type="json")

# --- Helper Functions ---
def convert_jalali_to_gregorian(jalali_date_str):
    try:
        if not jalali_date_str or len(jalali_date_str) < 8: return None
        parts = jalali_date_str.split('/')
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return jdatetime.date(y, m, d).togregorian()
    except: return None
    return None

def analyze_ads_with_gemini(ads_list, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # --- UPDATED PROMPT ---
    prompt_intro = """
    You are a legal expert in Iranian Corporate Law. Analyze the provided gazette notices.
    
    For each appointment, extract:
    1. "role_raw": The EXACT role description as written in the Persian text (e.g., "مدیرعامل و عضو هیئت مدیره" or "رئیس هیات مدیره").
    2. "role_standardized": Map the role to one of these: ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره", "عضو هیئت مدیره", "مدیرعامل و عضو هیئت مدیره", "بازرس اصلی", "بازرس علی‌البدل"].
    
    Rules:
    - Board Member tenure: 2 years (unless specified).
    - Inspector tenure: 1 year.
    - Dates: Convert all to YYYY/MM/DD (Jalali).
    
    Return JSON format only:
    {
      "results": [
        {
          "company_id": "...",
          "company_name": "...",
          "person_name": "...",
          "national_id": "...",
          "role_raw": "Extract exact text here",
          "role_standardized": "Standardized category",
          "start_date": "YYYY/MM/DD",
          "end_date": "YYYY/MM/DD",
          "gazette_no": "..."
        }
      ]
    }
    
    Input Data:
    """
    
    simplified_ads = []
    for ad in ads_list:
        simplified_ads.append({
            "ad_text": ad.get("متن آگهی"),
            "gazette_date": ad.get("تاریخ روزنامه"),
            "gazette_no": ad.get("شماره روزنامه"),
            "company_id": ad.get("شناسه ملی شرکت"),
            "company_name": ad.get("نام شرکت")
        })
    
    full_prompt = prompt_intro + json.dumps(simplified_ads, ensure_ascii=False)
    
    with st.spinner('در حال تحلیل دقیق متن‌ها...'):
        try:
            response = model.generate_content(full_prompt)
            text_res = response.text.replace('```json', '').replace('```', '')
            return json.loads(text_res)
        except Exception as e:
            st.error(f"Error: {e}")
            return None

# --- Main Logic ---
if uploaded_file is not None and api_key:
    data = json.load(uploaded_file)
    companies = list(set([d.get("نام شرکت") for d in data]))
    selected_company = st.selectbox("انتخاب شرکت", companies)
    
    if st.button("شروع پردازش"):
        analysis_result = analyze_ads_with_gemini(data, api_key)
        
        if analysis_result and "results" in analysis_result:
            results = analysis_result["results"]
            target_ids = set([d.get("شناسه ملی شرکت") for d in data if d.get("نام شرکت") == selected_company])
            
            # Filter logic
            company_people = [p for p in results if p.get("company_name") == selected_company or p.get("company_id") in target_ids]
            
            # --- Construct Final JSON with BOTH roles ---
            final_json = {
                "نام شرکت": selected_company,
                "شناسه شرکت": list(target_ids)[0] if target_ids else "",
                "اعضای شرکت": []
            }
            
            for p in company_people:
                final_json["اعضای شرکت"].append({
                    "نام": p.get("person_name"),
                    "کد ملی": p.get("national_id"),
                    "سمت_دقیق": p.get("role_raw"),           # <--- New Field
                    "سمت_استاندارد": p.get("role_standardized"), # <--- Standard Field
                    "تاریخ شروع": p.get("start_date"),
                    "تاریخ پایان": p.get("end_date"),
                    "شماره روزنامه": p.get("gazette_no")
                })
            
            # Display & Download
            st.subheader("خروجی JSON (شامل سمت دقیق و استاندارد)")
            st.json(final_json, expanded=False)
            st.download_button("دانلود JSON", json.dumps(final_json, ensure_ascii=False, indent=2), f"{selected_company}_full.json", "application/json")
            
            # --- Visualization ---
            df = pd.DataFrame(final_json["اعضای شرکت"])
            df['Start_Gregorian'] = df['تاریخ شروع'].apply(convert_jalali_to_gregorian)
            df['End_Gregorian'] = df['تاریخ پایان'].apply(convert_jalali_to_gregorian)
            df = df.dropna(subset=['Start_Gregorian'])
            
            # Main Board Timeline
            board_roles = ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره", "عضو هیئت مدیره", "مدیرعامل و عضو هیئت مدیره"]
            df_board = df[df['سمت_استاندارد'].isin(board_roles)]
            
            if not df_board.empty:
                st.subheader("تایم‌لاین اعضای هیئت مدیره")
                fig = px.timeline(
                    df_board,
                    x_start="Start_Gregorian",
                    x_end="End_Gregorian",
                    y="نام",
                    color="سمت_استاندارد", # Color by standard role for consistency
                    # Show the EXACT role in the tooltip
                    hover_data={
                        "سمت_دقیق": True, 
                        "شماره روزنامه": True, 
                        "Start_Gregorian": False, 
                        "End_Gregorian": False,
                        "تاریخ شروع": True,
                        "تاریخ پایان": True
                    },
                    title="تایم‌لاین مدیریتی (برای جزئیات موس را نگه دارید)"
                )
                fig.update_yaxes(categoryorder="total ascending")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("داده‌ای برای نمایش نمودار موجود نیست.")
