import streamlit as st
import base64
import json
import os
from gtts import gTTS
import io
from io import BytesIO
from datetime import datetime
import time
import pandas as pd
import google.generativeai as genai
from streamlit_option_menu import option_menu
from PIL import Image
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim
from datetime import datetime
from twilio.rest import Client


# ======================
# PATH AUR KEYS CONFIGURATION
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assests")
DATA_DIR = os.path.join(BASE_DIR, "data")

COMPLAINTS_FILE = os.path.join(DATA_DIR, "complaints.json")
TRUCKS_FILE = os.path.join(DATA_DIR, "trucks.json")

GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "default_pass")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ======================
# HELPER FUNCTIONS
# ======================
# ======================
# GOOGLE MAPS HELPER
# ======================
def create_google_maps_link(lat, lon):
    """
    Latitude aur Longitude se ek clickable Google Maps link banata hai.
    """
    if lat and lon:
        return f"https://www.google.com/maps?q={lat},{lon}"
    return "Exact location not available"
def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []
def get_address_from_coords(lat, lon):
    geolocator = Nominatim(user_agent="my_app")
    try:
        location = geolocator.reverse((lat, lon), language="en")
        if location and location.address:
            return location.address
        else:
            return "Unknown City"
    except:
        return "Unknown City"
def save_data(data, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_address_from_coords(lat, lon):
    try:
        geolocator = Nominatim(user_agent="safaisync_app_v3")
        location = geolocator.reverse((lat, lon), exactly_one=True)
        address = location.raw.get('address', {})
        road = address.get('road', '')
        suburb = address.get('suburb', '')
        city = address.get('city', 'Unknown City')
        if road and suburb:
            return f"{road}, {suburb}, {city}"
        if suburb:
            return f"{suburb}, {city}"
        return city
    except Exception:
        return "Address not found"
# ======================
# WHATSAPP HELPER FUNCTION (pywhatkit)
# ======================
def send_sms_twilio(phone_no, message):
    try:
        client = Client(
            st.secrets.get("TWILIO_ACCOUNT_SID"),
            st.secrets.get("TWILIO_AUTH_TOKEN")
        )
        message_obj = client.messages.create(
            body=message,
            from_=st.secrets.get("TWILIO_PHONE_NUMBER"),
            to=f"+{phone_no}"  # Country code zaroor add karein
        )
        print(f"SMS successfully sent to {phone_no}, SID: {message_obj.sid}")
        return True
    except Exception as e:
        st.error(f"SMS bhejte waqt masla hua: {e}")
        return False
# ======================
# IMAGE COMPRESSION
# ======================
def compress_image(image_file, max_size_kb=300):
    img = Image.open(image_file).convert("RGB")
    buf = BytesIO()
    quality = 85
    img.save(buf, format="JPEG", optimize=True, quality=quality)
    while buf.getbuffer().nbytes/1024 > max_size_kb and quality > 40:
        buf = BytesIO()
        quality -= 5
        img.save(buf, format="JPEG", optimize=True, quality=quality)
    return buf.getvalue()

# ======================
# AI WASTE ANALYSIS
# ======================
def get_ai_waste_analysis(image_bytes):
    if not GOOGLE_API_KEY:
        st.error("AI Assistant configure nahi hai.")
        return None
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-pro-vision')
        image_pil = Image.open(io.BytesIO(image_bytes))
        prompt_parts = [
            "Is tasveer ka tajziya karo. Pehli line mein 10 se 15 lafzon mein Roman Urdu mein batao ke tumhein is tasveer mein kya nazar aa raha hai (e.g., 'Is tasveer mein plastic ki bottles aur kaghaz hain.'). Dusri line mein, in options mein se sirf ek chuno: 'Household (Gharelu Kachra)', 'Construction Debris (Imarati Malba)', 'Plastic Waste', 'Organic (Gali Sarri Cheezein)', 'Other (Deegar)'.",
            image_pil,
        ]
        response = model.generate_content(prompt_parts)
        return response.text.strip()
    except Exception as e:
        st.error(f"Tasveer ka tajziya karte waqt masla hua: {e}")
        return None

# ======================
# AI TEXT EXPLANATION & AUDIO
# ======================
def get_ai_explanation_text(topic):
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Aap 'Safai Dost' hain. '{topic}' ke baare mein 1-2 aasan Roman Urdu ki lines mein batayein."
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"AI se rabta karte waqt masla hua: {e}")
        return "Mafi, abhi AI se rabta nahi ho pa raha. API key check karein."

def generate_and_play_audio_help(topic):
    if not GOOGLE_API_KEY:
        st.error("AI Assistant configure nahi hai.")
        return
    st.info(f"'{topic}' ke baare mein AI se poocha ja raha hai...")
    explanation_text = get_ai_explanation_text(topic)
    if "Mafi, abhi AI se rabta nahi ho pa raha" in explanation_text:
        return
    try:
        tts = gTTS(text=explanation_text, lang='ur', slow=False)
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        st.success("Suniye! 🔊")
        st.audio(audio_fp, autoplay=True)
    except Exception as e:
        st.error(f"Audio banane mein masla aa raha hai: {e}")

# ======================
# PRIORITY INFERENCE
# ======================
def infer_priority(explanation_text, amount):
    text = (explanation_text or "").lower()
    high_keys = ["stagnant", "pani", "drain", "hospital", "school", "animal", "gali sarri", "overflow"]
    if any(k in text for k in high_keys) or amount == "Large (Bohot Bara Dher)":
        return "High"
    if amount == "Medium (Darmiyana Dher)":
        return "Medium"
    return "Low"
# ===============================================
# === CUSTOM CSS FOR MINIMAL GREEN THEME (YAHAN SHAMIL KAREIN) ===
# ===============================================
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Ek aam CSS file ka path (agar aap alag file use karna chahein)
# local_css("style.css") 

# Ya seedha CSS code yahan likh dein
st.markdown("""
<style>
    /* Main app ka background color (config.toml se milta julta) */
    .main {
        background-color: #F0F2F6;
    }
    
    /* Buttons ko gol aur modern banayein */
    .stButton > button {
        border-radius: 20px;
        border: 2px solid #198754;
        color: #198754;
        background-color: #FFFFFF;
        transition: all 0.2s ease-in-out;
        font-weight: bold;
    }
    
    /* Button par mouse le jane ka effect */
    .stButton > button:hover {
        border-color: #146c43;
        color: #FFFFFF;
        background-color: #146c43;
        transform: scale(1.02);
    }
    
    /* Complaint Form ke har qadam ke liye container/card style */
    .step-container {
        border: 1px solid #e6e6e6;
        border-radius: 10px;
        padding: 25px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        background-color: #FFFFFF;
    }

    /* History page ke expander ka behtar style */
    .st-expander {
        border: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ======================
# APP CONFIGURATION
# ======================
# st.set_page_config(
#     page_title="SafaiSync -Your Companion",
#     page_icon="♻️",
#     layout="wide"
# )

# ======================
# HELPER FUNCTIONS (Data Loading)
# ======================
# ======================
# AI AUTO-ASSIGNMENT BRAIN
# ======================
def auto_assign_driver(complaint_location):
    """
    Complaint ki location ke hisab se sab se behtareen available driver dhoondta hai.
    """
    trucks = load_data(TRUCKS_FILE)
    
    # Pehle, sirf "Available" drivers ko filter karein
    available_trucks = [t for t in trucks if t.get('status') == 'Available']
    
    if not available_trucks:
        return None # Agar koi driver free nahi hai

    # Ab, in available drivers me se, location ke hisab se sab se acha dhoondein
    # Demo ke liye, hum simple area matching istemal karenge
    best_match = None
    for truck in available_trucks:
        truck_area = truck.get('area', '').lower()
        if truck_area in complaint_location.lower():
            best_match = truck # Jaise hi area match ho, usko chun lein
            break # Loop rok dein

    # Agar koi area match nahi hua, to koi bhi pehla available driver de dein
    if not best_match:
        best_match = available_trucks[0]
        
    return best_match
def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_data(data, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ======================
# LOCATION FUNCTION
# ======================

def get_address_from_coords(lat, lon):
    """
    Latitude aur Longitude se address hasil karta hai.
    Behtar fallback options: city, town, village, hamlet, suburb
    """
    try:
        geolocator = Nominatim(user_agent="safaisync_app_v3")
        location = geolocator.reverse((lat, lon), exactly_one=True)
        address = location.raw.get('address', {})

        road = address.get('road', '')
        suburb = address.get('suburb', '')
        city = address.get('city') or address.get('town') or address.get('village') or address.get('hamlet') or 'Unknown City'

        if road and suburb:
            return f"{road}, {suburb}, {city}"
        if suburb:
            return f"{suburb}, {city}"
        return city
    except Exception:
        return "Address not found"

# ======================
# AI WASTE ANALYSIS (Updated with Strict Options)
# ======================
def get_ai_waste_analysis(image_bytes):
    if not GOOGLE_API_KEY:
        st.error("AI Assistant configure nahi hai.")
        return None
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        image_pil = Image.open(io.BytesIO(image_bytes))

        # <-- YEH NAYA, ZYADA STRICT PROMPT HAI -->
        prompt_parts = [
            "Is tasveer ka 3 lines mein tajziya karo:\n"
            "1. Pehli line mein 10-15 lafzon mein Roman Urdu mein batao ke is tasveer mein kya nazar aa raha hai (e.g., 'Is tasveer mein plastic ki bottles, kaghaz aur gharelu kachra hai.').\n"
            "2. Dusri line mein, tasveer mein nazar anay walay kachre ki qism(ein) chuno. Aap ek se zyada bhi chun sakte hain, unhein comma se alag karein (e.g., Plastic Waste, Organic (Gali Sarri Cheezein)). SIRF in options mein se chunein: 'Household (Gharelu Kachra)', 'Construction Debris (Imarati Malba)', 'Plastic Waste', 'Organic (Gali Sarri Cheezein)', 'Other (Deegar)'.\n"
            "3. Teesri line mein, kachre ki miqdaar ka andaza lagao. SIRF in options mein se ek chuno: 'Small (Chota Dher)', 'Medium (Darmiyana Dher)', 'Large (Bohot Bara Dher)'.",
            image_pil,
        ]
        response = model.generate_content(prompt_parts)
        return response.text.strip()
    except Exception as e:
        st.error(f"Tasveer ka tajziya karte waqt masla hua: {e}")
        return None
           
# ======================
# STYLING AND HEADER
# ======================
logo_path = os.path.join(ASSETS_DIR, "Safaisync_logo.png")
logo_image = None
logo_encoded = ""
try:
    logo_image = Image.open(logo_path)
    with open(logo_path, "rb") as f:
        logo_encoded = base64.b64encode(f.read()).decode()
except FileNotFoundError:
    st.error("Logo file not found! Make sure 'SafaiSync_Project/assests/Safaisync_logo.png' exists.")

st.markdown(f"""
    <div style='background-color: #198754; padding: 1rem 2rem; border-radius: 12px; margin-bottom: 2rem; display: flex; align-items: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>
        <img src="data:image/png;base64,{logo_encoded}" style='width: 60px; margin-right: 15px;' />
        <div>
            <h1 style='color: white; margin: 0; font-size: 2.2rem;'>SafaiSync</h1>
            <p style='color: #d4edda; margin: 0;'>Your Partner for a Cleaner Pakistan</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# ======================
# AI AND AUDIO FUNCTIONS
# ======================
def get_ai_explanation_text(topic):
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Aap 'Safai Dost' hain. '{topic}' ke baare mein 1-2 aasan Roman Urdu ki lines mein batayein."
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Behtar error handling
        st.error(f"AI se rabta karte waqt masla hua: {e}")
        return "Mafi, abhi AI se rabta nahi ho pa raha. API key check karein."

def generate_and_play_audio_help(topic):
    """
    Gets explanation from Gemini, converts it to Urdu audio, and plays it.
    """
    # Simplified API key check
    if not GOOGLE_API_KEY:
        st.error("AI Assistant configure nahi hai. Baraye meharbani secrets mein API Key shamil karein.")
        return

    st.info(f"'{topic}' ke baare mein AI se poocha ja raha hai...")
    explanation_text = get_ai_explanation_text(topic)
    
    if "Mafi, abhi AI se rabta nahi ho pa raha" in explanation_text:
        return # Agar AI se text na miley to aage na barhein

    try:
        tts = gTTS(text=explanation_text, lang='ur', slow=False)
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        st.success("Suniye! 🔊")
        st.audio(audio_fp, autoplay=True)
    except Exception as e:
        st.error(f"Audio banane mein masla aa raha hai: {e}")

# ======================
# NAVIGATION
# ======================
with st.sidebar:
    if logo_image:
        st.image(logo_image, width=120)
    
    selected = option_menu(
        menu_title="Main Menu",
        options=["Home", "Report Complaint", "Complaint History", "Admin Panel"],
        icons=["house-door-fill", "camera-fill", "list-task", "person-shield"],
        menu_icon="list",
        default_index=0,
    )

# ======================
# PAGE DEFINITIONS
# ======================

def show_home():
    st.subheader("Welcome to the SafaiSync Initiative!")
    st.markdown("Hamara maqsad technology aur awami shirakat se ek saaf suthra aur sar sabz Pakistan banana hai.")

    st.info(
        "💔 **Kachra sirf gandagi nahi hai.** Yeh hamari sehat, mahol aur aanay wali naslon ke liye ek khatra hai. "
        "Yeh beemariyan phelata hai, pani ko alooda karta hai, aur shehron ki khubsurati ko tabah karta hai. "
        "**Aaiye, shikayat karne ke bajaye, charge lein aur mil kar isey theek karein!**"
    )

    col1, col2, col3 = st.columns(3)
    complaints = load_data(COMPLAINTS_FILE)
    total_complaints = len(complaints)
    resolved_complaints = len([c for c in complaints if c.get('status') == 'Resolved'])
    pending_complaints = total_complaints - resolved_complaints

    col1.metric("Total Complaints", f"{total_complaints} 🗑️")
    col2.metric("Complaints Resolved", f"{resolved_complaints} ✅")
    col3.metric("Pending Action", f"{pending_complaints} ⏳")

    # --- YAHAN HAI ASAL FIX ---
    # Hum ab naqli (hardcoded) list istemal nahi karenge
    st.subheader("📍 Live Complaints Map")
    
    complaints_with_coords = []
    for c in complaints:
        # Check karein ke complaint me latitude aur longitude maujood hain
        if 'latitude' in c and 'longitude' in c:
            complaints_with_coords.append({
                'lat': c['latitude'],
                'lon': c['longitude']
            })
    
    if complaints_with_coords:
        # Asal coordinates se DataFrame banayein
        map_data = pd.DataFrame(complaints_with_coords)
        st.map(map_data, zoom=11)
    else:
        st.write("Abhi naqshay par dikhane ke liye koi aisi shikayat mojood nahi jisme location save ho.")

# Report Complaint Page: integrate compressed image + priority
def show_report_form():
    st.subheader("📝 Take Action: Report a Waste Hotspot")
    st.markdown("3 aasan qadmon mein apne sheher ko saaf banane me hamari madad karein.")
    st.markdown("---")

    # Session State Initialization
    if 'user_address' not in st.session_state: st.session_state.user_address = None
    if 'suggested_type' not in st.session_state: st.session_state.suggested_type = None
    if 'suggested_amount' not in st.session_state: st.session_state.suggested_amount = None
    if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None

    # Qadam 1: Location (Yeh hissa waisa hi rahega)
    with st.container():
        st.markdown('<div class="step-container">', unsafe_allow_html=True)
        st.markdown("### 📍 Qadam 1: Apni Location Batayein")
        location_data = streamlit_geolocation()
        if st.button("Yahan Click Karke Apni Location Confirm Karein", key="confirm_loc_btn"):
            if location_data and location_data.get('latitude'):
                lat, lon = location_data['latitude'], location_data['longitude']
                address = get_address_from_coords(lat, lon)
                st.session_state.user_address = address
                st.session_state.user_lat = lat
                st.session_state.user_lon = lon
                st.success(f"✅ Location confirm ho gayi: **{address}**")
                time.sleep(1); st.rerun()
            else:
                st.error("❌ Location hasil nahi ho saki. Browser permission check karein.")
        if st.session_state.user_address:
            st.info(f"**Aapki Location:** {st.session_state.user_address}")
        else:
            st.warning("Upar diye gaye button ko click karne se pehle browser mein location ki ijazat lazmi dein.")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.user_address:
        # Qadam 2: Tasveer aur AI Analysis
        with st.container():
            st.markdown('<div class="step-container">', unsafe_allow_html=True)
            st.markdown("### 📸 Qadam 2: Kachre ki Tasveer Dein")
            uploaded_file = st.file_uploader("Yahan tasveer upload karein", type=["jpg","jpeg","png"], key="uploader")
            
            if uploaded_file is not None:
                st.session_state.uploaded_file_bytes = uploaded_file.getvalue()
                st.image(st.session_state.uploaded_file_bytes, caption="Aapki upload karda tasveer.", width=300)
                
                if st.button("Tasveer se Kachre ka Tajziya Karein", key="analyze_btn"):
                    with st.spinner("AI tasveer ka tajziya kar raha hai..."):
                        st.session_state.analysis_result = get_ai_waste_analysis(st.session_state.uploaded_file_bytes)
                        if st.session_state.analysis_result:
                            # <-- YAHAN HAI ASAL FIX -->
                            # 1. AI ke jawab ko lines me torein
                            lines = st.session_state.analysis_result.split('\n')
                            # 2. Sirf un lines ko rakhein jo khali nahi hain
                            clean_lines = [line.strip() for line in lines if line.strip()]
                            
                            # 3. Ab 'clean_lines' se data uthayein
                            if len(clean_lines) >= 3:
                                explanation = clean_lines[0]
                                st.session_state.suggested_type = clean_lines[1]
                                st.session_state.suggested_amount = clean_lines[2]
                                
                                st.info(f"🤖 **AI Tajziya:** {explanation}")
                                st.success(f"✅ **Tajweez Karda Qisam(ein):** '{st.session_state.suggested_type}'")
                                st.success(f"✅ **Andazan Miqdaar:** '{st.session_state.suggested_amount}'")
                            else:
                                st.error("AI se poora jawab nahi mila. Dobara koshish karein.")
                                st.write("AI ka raw jawab:", st.session_state.analysis_result) # Debugging ke liye
                        else:
                            st.error("AI is tasveer ka tajziya nahi kar saka.")
            st.markdown('</div>', unsafe_allow_html=True)

        # Qadam 3: Submission (Isme koi change nahi, yeh ab khud theek kaam karega)
        with st.container():
            st.markdown('<div class="step-container">', unsafe_allow_html=True)
            st.markdown("### 🚀 Qadam 3: Action Mukammal Karein")
            with st.form("complaint_final_form"):
                st.text_input("Kachre ki Qisam(ein) (AI ne detect ki)", value=st.session_state.get('suggested_type', 'Abhi tak detect nahi hui'), disabled=True)
                st.text_input("Kachre ki Miqdaar (AI ne detect ki)", value=st.session_state.get('suggested_amount', 'Abhi tak detect nahi hui'), disabled=True)
                
                submitted = st.form_submit_button("Shikayat Jama Karein")
                if submitted:
                    # Session state se zaroori data hasil karein
                    final_uploaded_file_bytes = st.session_state.get('uploaded_file_bytes')
                    waste_type = st.session_state.get('suggested_type')
                    garbage_amount = st.session_state.get('suggested_amount')
                    
                    # Check karein ke tamam zaroori qadam mukammal ho chuke hain
                    if st.session_state.user_address and final_uploaded_file_bytes and waste_type and garbage_amount:
                        
                        # ===================================================
                        # === NAYI AUTONOMOUS LOGIC YAHAN SE SHURU HOTI HAI ===
                        # ===================================================

                        # 1. Pehle complaint ka buniyadi data tayyar karein
                        img_bytes_compressed = compress_image(io.BytesIO(final_uploaded_file_bytes))
                        explanation_text = st.session_state.analysis_result.split('\n')[0] if st.session_state.analysis_result else ""
                        priority_level = infer_priority(explanation_text, garbage_amount)
                        
                        # 2. AI Brain (helper function) ko call karke sab se behtareen driver dhoondein
                        assigned_truck_details = auto_assign_driver(st.session_state.user_address)
                        
                        # 3. Faisla karein ke driver mila ya nahi
                        if assigned_truck_details:
                            # Agar driver mil gaya hai
                            assigned_to_str = f"{assigned_truck_details['driver_name']} ({assigned_truck_details['truck_id']})"
                            new_status = "In Progress" # Status khud hi "In Progress" kar dein
                            driver_phone = assigned_truck_details['phone_no']
                            driver_name = assigned_truck_details['driver_name']
                            
                            st.info(f"System ne is complaint ko Priority '{priority_level}' di hai aur automatically {driver_name} ko assign kar diya hai.")
                            st.info("Driver ko WhatsApp notification bheja ja raha hai...")

                            # 4. Driver ko foran WhatsApp message bhej dein
                            maps_link = create_google_maps_link(st.session_state.user_lat, st.session_state.user_lon)
                            message_body = (
                                f"Assalam o Alaikum {driver_name},\n\n"
                                f"**AUTO-ASSIGNMENT:** Aapko ek nayi complaint fori assign ki gayi hai:\n\n"
                                f"🆔 Complaint ID: #{len(load_data(COMPLAINTS_FILE)) + 1}\n"
                                f"🚦 Priority: *{priority_level}*\n"
                                f"📍 Location: {st.session_state.user_address}\n"
                                f"🗺️ Maps Link: {maps_link}\n\n"
                                f"Baraye meharbani fori karwai karein."
                            )
                            send_sms_twilio(driver_phone, message_body)
                            st.success("✅ Driver ko notification bhej diya gaya hai!")

                        else:
                            # Agar koi driver free nahi hai
                            assigned_to_str = "None (No Driver Available)"
                            new_status = "Pending"
                            st.warning(f"⚠️ Is complaint ko Priority '{priority_level}' di gayi hai, lekin koi bhi driver is waqt available nahi hai. Complaint ko 'Pending' me daal diya gaya hai.")

                        # 5. Aakhir me, nayi complaint ko poori details ke saath save karein
                        complaints = load_data(COMPLAINTS_FILE)
                        new_complaint = {
                            "id": len(complaints) + 1,
                            "type": waste_type,
                            "location": st.session_state.user_address,
                            "latitude": st.session_state.user_lat,   
                            "longitude": st.session_state.user_lon,
                            "amount": garbage_amount,
                            "priority": priority_level,
                            "timestamp": datetime.now().strftime("%B %d, %Y %I:%M %p"),
                            "status": new_status, # Yahan naya, smart status aayega
                            "assigned_to": assigned_to_str, # Yahan naya, smart assignment aayega
                            "image_data": base64.b64encode(img_bytes_compressed).decode('utf-8')
                        }
                        complaints.append(new_complaint)
                        save_data(complaints, COMPLAINTS_FILE)

                        st.success("✅ Aapka action kamyabi se record aur process ho gaya hai!")
                        st.balloons()
                    
                    else:
                        st.warning("⚠️ Baraye meharbani, tamam qadam mukammal karein (Location aur Tasveer ka Tajziya).")


def show_history():
    st.subheader("📜 My Complaints History")
    complaints = load_data(COMPLAINTS_FILE)

    if not complaints:
        st.info("Aapne abhi tak koi action nahi liya. 'Take Action & Report' page par ja kar shuru karein.")
        return

    status_filter = st.selectbox("Status ke hisab se filter karein:", ["All", "Pending", "In Progress", "Resolved"])

    filtered_complaints = [c for c in complaints if status_filter == "All" or c.get('status') == status_filter]
    
    if not filtered_complaints:
        st.write(f"'{status_filter}' status ke saath koi complaint mojood nahi.")
        return

    # Complaints ko reverse order me dikhayein (sabse nayi sabse upar)
    for comp in reversed(filtered_complaints):
        with st.expander(f"Complaint #{comp.get('id', 'N/A')} - {comp.get('location', 'N/A')} ({comp.get('status', 'N/A')})"):
            st.markdown(f"**🗓️ Tareekh:** {comp.get('timestamp', 'N/A')}")
            col1, col2 = st.columns(2)
            
            with col1:
                if comp.get('image_data'):
                    try:
                        image_bytes = base64.b64decode(comp['image_data'])
                        st.image(image_bytes, caption="Jama Shuda Tasveer", use_column_width=True)
                    except Exception as e:
                        st.error(f"Tasveer load nahi ho saki: {e}")
            
            with col2:
                st.markdown(f"**🚮 Waste Type:** {comp.get('type', 'N/A')}")
                st.markdown(f"**🎚️ Miqdaar:** {comp.get('amount', 'N/A')}")
                st.markdown(f"**🚦 Status:** {comp.get('status', 'N/A')}")
                st.markdown(f"**🚚 Assigned To:** {comp.get('assigned_to', 'N/A')}")

            # --- DELETE BUTTON LOGIC ---
            st.markdown("---")
            if st.button("Delete This Complaint", key=f"delete_{comp.get('id', 'N/A')}", type="primary"):
                # Load all complaints again to ensure we have the latest data
                all_complaints = load_data(COMPLAINTS_FILE)
                # Create a new list, keeping all complaints EXCEPT the one with the matching ID
                complaints_to_keep = [c for c in all_complaints if c.get('id') != comp.get('id')]
                # Save the updated list back to the file
                save_data(complaints_to_keep, COMPLAINTS_FILE)
                
                st.success(f"Complaint #{comp.get('id')} delete ho gayi hai.")
                time.sleep(1) # Thora wait karein taake user message parh le
                st.rerun() # Page ko refresh karein taake list update ho jaye

def show_admin_panel():
    st.subheader("🔐 Admin Panel")
    st.warning("Yeh section sirf admin ke liye hai.")
    password = st.text_input("Admin Password Darj Karein", type="password", key="admin_password")

    if password == ADMIN_PASSWORD:
        st.success("Access Granted! Welcome Admin.")
        st.markdown("---")

        complaints = load_data(COMPLAINTS_FILE)
        trucks = load_data(TRUCKS_FILE)
        # Sirf naam aur ID se options banayein
        truck_options = [f"{truck['driver_name']} ({truck['truck_id']})" for truck in trucks]

        st.header("Master Complaint Dashboard")
        if not complaints:
            st.info("Abhi tak koi shikayat nahi hai.")
            return # Agar koi complaint nahi to function yahin rok dein

        for complaint in sorted(complaints, key=lambda x: x['id'], reverse=True):
            st.markdown(f"#### Complaint #{complaint['id']} ({complaint['status']})")
            col1, col2 = st.columns(2)
            
            with col1:
                st.image(base64.b64decode(complaint['image_data']), use_column_width=True)
                st.write(f"**Location:** {complaint['location']}")
                st.write(f"**Date:** {complaint['timestamp']}")
            
            with col2:
                new_status = st.selectbox(
                    "Update Status",
                    ["Pending", "In Progress", "Resolved"],
                    key=f"status_{complaint['id']}",
                    index=["Pending", "In Progress", "Resolved"].index(complaint.get('status', 'Pending'))
                )
                
                assigned_truck_str = st.selectbox(
                    "Assign Available Truck",
                    ["None"] + truck_options, # "None" ka option zaroori hai
                    key=f"truck_{complaint['id']}"
                )

                # Button ka text badal dein taake pata chale ke isse notification jayega
                if st.button("Save Changes & Notify Driver", key=f"save_{complaint['id']}"):
                    
                    # 1. Pehle complaint data update karein aur save karein
                    for c in complaints:
                        if c['id'] == complaint['id']:
                            c['status'] = new_status
                            c['assigned_to'] = assigned_truck_str
                            break
                    save_data(complaints, COMPLAINTS_FILE)
                    st.success(f"Complaint #{complaint['id']} ki details database me save ho gayi hain!")
                    
                    # 2. Ab check karein ke kya koi truck assign hua hai
                    if assigned_truck_str != "None":
                        
                        # 3. Assign kiye gaye truck ki poori details (phone number samet) hasil karein
                        selected_truck_details = None
                        for truck in trucks:
                            if f"{truck['driver_name']} ({truck['truck_id']})" == assigned_truck_str:
                                selected_truck_details = truck
                                break
                        
                        if selected_truck_details:
                            driver_phone = selected_truck_details['phone_no']
                            driver_name = selected_truck_details['driver_name']
                            
                            # 4. Driver ke liye ek khoobsurat message banayein
                            lat = complaint.get('latitude')
                            lon = complaint.get('longitude')
                            maps_link = create_google_maps_link(lat, lon)
                            message_body = (
                                f"Assalam o Alaikum {driver_name},\n\n"
                                f"Aapko ek nayi SafaiSync complaint assign ki gayi hai:\n\n"
                                f"🆔 *Complaint ID:* #{complaint['id']}\n"
                                f"🚦 *Priority:* {complaint['priority']}\n"
                                f"📍 *Location Address:* {complaint['location']}\n\n" 
                                f"🗺️ *EXACT LOCATION LINK:*\n"  
                                f"{maps_link}\n\n" 
                                f"Baraye meharbani fori karwai karein."
                            )
                            
                            st.info(f"Driver {driver_name} ko WhatsApp bheja ja raha hai... (Isme 1-2 minute lag sakte hain)")
                            
                            # 5. Hamara helper function call karein jo message bhejega
                            success = send_sms_twilio(driver_phone, message_body)
                            
                            if success:
                                st.success("✅ Driver ko WhatsApp notification schedule ho gaya hai! Browser check karein.")
                        else:
                            st.error(f"Error: Driver '{assigned_truck_str}' ki details 'trucks.json' me nahi milein.")
                    
                    # Aakhir me, page ko refresh karein taake sab kuch update ho jaye
                    time.sleep(2) # 2 second ka wait taake user messages parh le
                    st.rerun()

    elif password and password != ADMIN_PASSWORD:
        st.error("Ghalat Password. Access Denied.")

# ======================
# PAGE ROUTING LOGIC
# ======================
if selected == "Home":
    show_home()
elif selected == "Report Complaint":
    show_report_form()
elif selected == "Complaint History":
    show_history()
elif selected == "Admin Panel":
    show_admin_panel()