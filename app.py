import streamlit as st
import google.generativeai as genai
import os
import tempfile
from datetime import datetime, timedelta
import json

# Configure Gemini API
GEMINI_API_KEY = st.sidebar.text_input("Enter your Google Gemini API Key", type="password")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    st.warning("Please enter your Gemini API Key in the sidebar to enable AI suggestions.")

# Session state
if 'progress_data' not in st.session_state:
    st.session_state.progress_data = []
if 'current_exercises' not in st.session_state:
    st.session_state.current_exercises = []
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {"weak_muscles": [], "fall_risk": "low", "pain_areas": [], "metrics": {}}
if 'pain_flags' not in st.session_state:
    st.session_state.pain_flags = []
if 'performed_movements' not in st.session_state:
    st.session_state.performed_movements = set()
if 'exercise_feedbacks' not in st.session_state:
    st.session_state.exercise_feedbacks = []
if 'exercise_index' not in st.session_state:
    st.session_state.exercise_index = 0
if 'show_rating' not in st.session_state:
    st.session_state.show_rating = False

# Calming Theme with Darker Green, Black Lines, Abstract Browns
st.markdown("""
<style>
    .stApp {
        background-color: #f8f5f0;  /* light beige with brown tint */
        border: 2px solid #333333;  /* black border around page */
    }
    .stButton>button {
        background-color: #4a7c59;  /* darker calming green */
        color: white;
        border: 1px solid #333333;
    }
    h1, h2, h3 {
        color: #3e5f4a;  /* darker green */
    }
    .stSelectbox, .stTextInput, .stSlider {
        background-color: #e8e4d8;  /* soft brown-beige */
        border: 1px solid #666666;
    }
    .stMarkdown {
        color: #2d3f3a;  /* dark teal-gray */
    }
    hr {
        border-color: #333333;  /* black lines */
        height: 2px;
    }
    .pain-card {
        background-color: #e8e4d8;
        padding: 20px;
        border-radius: 15px;
        border: 2px solid #333333;
    }
</style>
""", unsafe_allow_html=True)

st.title("My Personal PT Coach")
st.markdown("### AI-Powered Physical Therapy • Personalized • Safe")

# Check for weekly reassessment
if st.session_state.step == 0 and st.session_state.progress_data:
    last_entry = st.session_state.progress_data[-1]
    last_date = datetime.strptime(last_entry["date"], "%Y-%m-%d %H:%M")
    if datetime.now() - last_date > timedelta(days=7):
        st.info("🌟 It's time for your weekly reassessment to track progress!")
        if st.button("Start Weekly Reassessment"):
            st.session_state.step = 1
            st.rerun()

# Video analysis function (unchanged)
def analyze_video(video_path, movement_type, variant=None):
    uploaded_file = genai.upload_file(video_path)
    variant_str = f" ({variant})" if variant else ""
    prompt = f"""
    Analyze this video for {movement_type}{variant_str} assessment in a physical therapy context.
    Detect and quantify:
    - Counts (e.g., steps, squats)
    - Depths/angles (e.g., squat depth in degrees, asymmetries in hips/knees)
    - Balance time and stability (wobble score, lower better)
    - Asymmetries (hip, knee in degrees)
    - Likely weak muscles based on form, imbalances, or shallow movements
    - Fall risk: low, medium, high based on balance and asymmetries
    
    Output as JSON with keys: 
    - metrics: dict
    - weak_muscles: list of strings
    - fall_risk: string (low/medium/high)
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt, uploaded_file])
    try:
        analysis = json.loads(response.text.strip('```json\n').strip('```'))
    except:
        st.error("Analysis failed. Try a shorter, clearer video.")
        analysis = {"weak_muscles": [], "fall_risk": "low", "metrics": {}}
    genai.delete_file(uploaded_file.name)
    return analysis

def update_analysis(new_analysis, movement_type):
    for w in new_analysis["weak_muscles"]:
        if w not in st.session_state.analysis_results["weak_muscles"]:
            st.session_state.analysis_results["weak_muscles"].append(w)
    fall_num = {"low": 1, "medium": 2, "high": 3}
    current = st.session_state.analysis_results["fall_risk"]
    if fall_num[new_analysis["fall_risk"]] > fall_num[current]:
        st.session_state.analysis_results["fall_risk"] = new_analysis["fall_risk"]
    st.session_state.analysis_results["metrics"][movement_type] = new_analysis["metrics"]
    st.session_state.performed_movements.add(movement_type)

# Step 0: Initial Assessment
if st.session_state.step == 0:
    st.subheader("Welcome! Let's Get Started")
    st.write("We’ll create a safe, personalized plan just for you.")

    # First Name (now REQUIRED) and Gender
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name *", placeholder="Required")
    with col2:
        gender = st.selectbox("Gender *", ["Male", "Female"])

    st.markdown("---")

    # Vertical Age Picker - using number input with large step for wheel feel (best workaround in Streamlit)
    st.markdown("**Your Age**")
    age = st.number_input("Select your age (use arrows or scroll)", min_value=18, max_value=100, value=40, step=1)
    st.markdown(f"<h4 style='text-align: center; color: #3e5f4a;'>Selected: {age} years</h4>", unsafe_allow_html=True)

    st.markdown("---")

    # Wong-Baker Pain Scale - Horizontal slider + Real Full Chart Image
    st.markdown("**Current Pain Level**")
    pain_level = st.slider("", min_value=0, max_value=10, value=0, step=2, label_visibility="collapsed")

    # Real high-quality full Wong-Baker scale image
    st.markdown("<div class='pain-card'>", unsafe_allow_html=True)
    st.image("https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/2258701-wong-baker-pain-scale-header-1296x728-1-1024x575.jpg?w=1155&h=1528", use_column_width=True)
    st.markdown(f"<h4 style='text-align: center; color: #3e5f4a;'>Your current pain: {pain_level}/10</h4>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Main reason
    chief_complaint_type = st.selectbox("Main reason you're here today", ["Pain", "Balance issues"])

    # Safety recommendation
    if age > 50 or pain_level > 4:
        st.info("🛡️ We'll recommend gentle, seated-friendly exercises for safety. You can override if comfortable.")
        override = st.checkbox("I prefer standing exercises")
        seated_recommended = not override
    else:
        seated_recommended = False
        override = False

    # Require first name
    if not first_name.strip():
        st.error("First name is required to continue.")
    elif st.button("Continue to Movement Check →"):
        st.session_state.user_data = {
            "first_name": first_name.strip(),
            "gender": gender,
            "age": age,
            "baseline_pain": pain_level,
            "chief_complaint_type": chief_complaint_type,
            "seated_recommended": seated_recommended,
            "override": override
        }
        st.session_state.step = 1
        st.rerun()

# Steps 1–5 remain the same (keep from your previous code)

st.caption("Always consult a healthcare professional. This app is for educational use.")
