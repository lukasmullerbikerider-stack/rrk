import streamlit as st
import json
import pandas as pd
import plotly.express as px
from google import genai
from google.genai import types
import jdatetime

# --- Page Config ---
st.set_page_config(page_title="تحلیلگر حقوقی هوشمند (GenAI SDK)", layout="wide")

st.title("⚖️ تحلیلگر پیشرفته روزنامه رسمی")
st.markdown("با استفاده از **Gemini 2.0/3.0** و قابلیت **Thinking** برای استخراج دقیق سمت‌های حقوقی")

# --- Sidebar ---
st.sidebar.header("تنظیمات")
api_key = st.sidebar.text_input("Gemini API Key", type="password")
model_name = st.sidebar.selectbox("انتخاب مدل", ["gemini-2.5-pro", "gemini-2.5-flash"])
uploaded_file = st.sidebar.file_uploader("آپلود فایل JSON روزنامه رسمی", type="json")

# --- Helper Functions ---
def convert_jalali_to_gregorian(jalali_date_str):
    """Convert Jalali date string to Gregorian for plotting."""
    try:
        if not jalali_date_str or len(jalali_date_str) < 8: return None
        # Clean up string if needed
        jalali_date_str = jalali_date_str.strip()
        parts = jalali_date_str.split('/')
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return jdatetime.date(y, m, d).togregorian()
    except: return None
    return None

def analyze_ads_advanced(ads_list, api_key, model_id):
    """Analyzes ads using the new google.genai client with ThinkingConfig."""
    
    client = genai.Client(api_key=api_key)
    
    # --- System Prompt ---
    prompt_text = """
    You are an expert Legal Analyst for Iranian Official Gazette (Roznameh Rasmi).
    
    Your Task: Analyze the list of company advertisement texts provided in JSON format.
    
    Extract the following information for each appointed individual or entity:
    1. **person_name**: Name of the person or entity.
    2. **national_id**: National ID (Code Melli/Shenase Melli).
    3. **role_raw**: The EXACT role description as written in the Persian text (e.g., "مدیرعامل و عضو هیئت مدیره").
    4. **role_standardized**: Standardize the role to one of: ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره", "عضو هیئت مدیره", "مدیرعامل و عضو هیئت مدیره", "بازرس اصلی", "بازرس علی‌البدل"].
    5. **start_date**: The date of the meeting/appointment (Persian YYYY/MM/DD).
    6. **end_date**: The end date of tenure. 
       - Logic: If text says "for 2 years", add 2 years to start_date. If "for 1 year" (inspectors), add 1 year.
    7. **gazette_no**: The gazette number.

    Output Schema (JSON):
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
    
    Input Data:
    """
    
    # Prepare data for prompt (simplify to reduce tokens if needed)
    simplified_ads = []
    for ad in ads_list:
        simplified_ads.append({
            "text": ad.get("متن آگهی"),
            "date": ad.get("تاریخ روزنامه"),
            "number": ad.get("شماره روزنامه"),
            "company_id": ad.get("شناسه ملی شرکت"),
            "company_name": ad.get("نام شرکت")
        })
    
    full_content = prompt_text + json.dumps(simplified_ads, ensure_ascii=False)

    try:
        with st.spinner('در حال تفکر و تحلیل عمیق (Thinking Mode)...'):
            # --- The New Client Call Style ---
            response = client.models.generate_content(
                model=model_id,
                contents=full_content,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    # Enable Thinking for complex logic extraction
                    thinking_config=types.ThinkingConfig(thinking_level="low") if "thinking" in model_id else None
                ),
            )
            return json.loads(response.text)
            
    except Exception as e:
        st.error(f"Error during analysis: {e}")
        return None

# --- Main Logic ---

if uploaded_file and api_key:
    data = json.load(uploaded_file)
    
    # 1. Company Selection
    companies = list(set([d.get("نام شرکت") for d in data]))
    selected_company = st.selectbox("شرکت مورد نظر را انتخاب کنید:", companies)
    
    # 2. Process Button
    if st.button("اجرای تحلیل هوشمند"):
        # Filter raw data for context (optional: send all to let AI decide, but sending relevant helps tokens)
        # Here we send all because names might change slightly
        
        result_json = analyze_ads_advanced(data, api_key, model_name)
        
        if result_json and "results" in result_json:
            results = result_json["results"]
            
            # Filter results for selected company name or ID matches
            target_ids = set([d.get("شناسه ملی شرکت") for d in data if d.get("نام شرکت") == selected_company])
            
            final_people = [
                p for p in results 
                if p.get("company_name") == selected_company or p.get("company_id") in target_ids
            ]
            
            # --- Build Final Output Format ---
            output_data = {
                "نام شرکت": selected_company,
                "شناسه شرکت": list(target_ids)[0] if target_ids else "",
                "اعضای شرکت": []
            }
            
            for p in final_people:
                output_data["اعضای شرکت"].append({
                    "نام": p.get("person_name"),
                    "کد ملی": p.get("national_id"),
                    "سمت_دقیق": p.get("role_raw"),
                    "سمت_استاندارد": p.get("role_standardized"),
                    "تاریخ شروع": p.get("start_date"),
                    "تاریخ پایان": p.get("end_date"),
                    "شماره روزنامه": p.get("gazette_no")
                })
            
            # --- Show & Download JSON ---
            st.success("تحلیل کامل شد!")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("خروجی JSON")
                st.json(output_data, expanded=False)
            
            with col2:
                st.download_button(
                    label="📥 دانلود فایل JSON نهایی",
                    data=json.dumps(output_data, ensure_ascii=False, indent=2),
                    file_name=f"{selected_company}_analyzed.json",
                    mime="application/json"
                )
            
            # --- Visualization (Timelines) ---
            st.divider()
            
            df = pd.DataFrame(output_data["اعضای شرکت"])
            
            if not df.empty:
                # Prepare dates
                df['Start_Gregorian'] = df['تاریخ شروع'].apply(convert_jalali_to_gregorian)
                df['End_Gregorian'] = df['تاریخ پایان'].apply(convert_jalali_to_gregorian)
                df = df.dropna(subset=['Start_Gregorian', 'End_Gregorian'])
                
                # 1. Board Members Timeline
                board_roles = ["مدیرعامل", "رئیس هیئت مدیره", "نایب رئیس هیئت مدیره", "عضو هیئت مدیره", "مدیرعامل و عضو هیئت مدیره"]
                df_board = df[df['سمت_استاندارد'].isin(board_roles)]
                
                if not df_board.empty:
                    st.subheader("📊 تایم‌لاین اعضای هیئت مدیره")
                    fig_board = px.timeline(
                        df_board, 
                        x_start="Start_Gregorian", 
                        x_end="End_Gregorian", 
                        y="نام", 
                        color="سمت_استاندارد",
                        hover_data={"سمت_دقیق": True, "شماره روزنامه": True},
                        title="دوره تصدی اعضای اصلی"
                    )
                    fig_board.update_yaxes(categoryorder="total ascending")
                    st.plotly_chart(fig_board, use_container_width=True)
                
                # 2. All Members Timeline
                st.subheader("📊 تایم‌لاین کلیه اعضا (شامل بازرسین)")
                fig_all = px.timeline(
                    df, 
                    x_start="Start_Gregorian", 
                    x_end="End_Gregorian", 
                    y="نام", 
                    color="سمت_استاندارد",
                    hover_data={"سمت_دقیق": True, "شماره روزنامه": True},
                    title="دوره تصدی تمامی نقش‌ها"
                )
                fig_all.update_yaxes(categoryorder="total ascending")
                st.plotly_chart(fig_all, use_container_width=True)
                
        else:
            st.warning("خروجی معتبری دریافت نشد یا ساختار فایل با مدل همخوانی نداشت.")

elif not api_key:
    st.info("👈 لطفاً کلید API را از منوی سمت چپ وارد کنید.")
