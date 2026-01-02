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
    st.session_feedbacks = []
if 'exercise_index' not in st.session_state:
    st.session_state.exercise_index = 0
if 'show_rating' not in st.session_state:
    st.session_state.show_rating = False

# Calming Custom Theme: Soft Green, Blue, Beige
st.markdown("""
<style>
    .stApp {
        background-color: #f5f7f6;  /* light beige-gray */
    }
    .stButton>button {
        background-color: #a7c4bc;  /* soft green */
        color: white;
    }
    h1, h2, h3 {
        color: #2e7d7d;  /* deep teal green */
    }
    .stSelectbox, .stTextInput, .stSlider {
        background-color: #e8f0ee;  /* very light green-beige */
    }
    .stMarkdown {
        color: #3d5a80;  /* calm blue-gray */
    }
    hr {
        border-color: #b8d4d0;
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

# Video analysis function
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

    # First Name and Gender (no "Prefer not to say")
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name (optional)")
    with col2:
        gender = st.selectbox("Gender", ["Male", "Female"])

    st.markdown("---")

    # Vertical Age Scroll Wheel (fixed with better CSS)
    st.markdown("**Your Age**")
    age_options = list(range(18, 101))
    age = st.select_slider(
        "Scroll up/down to select your age",
        options=age_options,
        value=40,
        label_visibility="collapsed"
    )
    st.markdown(f"<h4 style='text-align: center; color: #2e7d7d;'>Selected age: {age} years</h4>", unsafe_allow_html=True)

    # Improved CSS for true vertical wheel
    st.markdown("""
    <style>
        div[data-testid="stSelectSlider"] > div[data-baseweb="slider"] {
            flex-direction: column !important;
            height: 350px !important;
            align-items: center;
        }
        div[data-testid="stSelectSlider"] div[role="listbox"] {
            max-height: 300px !important;
            overflow-y: auto !important;
            width: 200px;
        }
        div[data-testid="stSelectSlider"] div[data-baseweb="slider"] > div {
            width: 100% !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Wong-Baker Pain Scale as Horizontal Slider with Real Faces Underneath
    st.markdown("**Current Pain Level**")
    pain_level = st.slider(
        "Slide to select your pain level",
        min_value=0,
        max_value=10,
        value=0,
        step=2,
        label_visibility="collapsed"
    )

    # Real Wong-Baker faces (high-quality from Medical News Today)
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; margin-top: 30px; padding: 20px; background-color: #e8f0ee; border-radius: 15px;">
        <div style="text-align:center;"><img src="https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/wong-baker-face-0-732x549-thumbnail.jpg" width="90"><br><strong>0</strong><br>No hurt</div>
        <div style="text-align:center;"><img src="https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/wong-baker-face-2-732x549-thumbnail.jpg" width="90"><br><strong>2</strong><br>Hurts little bit</div>
        <div style="text-align:center;"><img src="https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/wong-baker-face-4-732x549-thumbnail.jpg" width="90"><br><strong>4</strong><br>Hurts little more</div>
        <div style="text-align:center;"><img src="https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/wong-baker-face-6-732x549-thumbnail.jpg" width="90"><br><strong>6</strong><br>Hurts even more</div>
        <div style="text-align:center;"><img src="https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/wong-baker-face-8-732x549-thumbnail.jpg" width="90"><br><strong>8</strong><br>Hurts whole lot</div>
        <div style="text-align:center;"><img src="https://post.medicalnewstoday.com/wp-content/uploads/sites/3/2022/12/wong-baker-face-10-732x549-thumbnail.jpg" width="90"><br><strong>10</strong><br>Hurts worst</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Main reason - only Pain or Balance issues
    chief_complaint_type = st.selectbox("Main reason you're here today", ["Pain", "Balance issues"])

    # Safety recommendation
    if age > 50 or pain_level > 4:
        st.info("🛡️ We'll recommend gentle, seated-friendly exercises for safety. You can override if comfortable.")
        override = st.checkbox("I prefer standing exercises")
        seated_recommended = not override
    else:
        seated_recommended = False
        override = False

    if st.button("Continue to Movement Check →"):
        st.session_state.user_data = {
            "first_name": first_name,
            "gender": gender,
            "age": age,
            "baseline_pain": pain_level,
            "chief_complaint_type": chief_complaint_type,
            "seated_recommended": seated_recommended,
            "override": override
        }
        st.session_state.step = 1
        st.rerun()

# The rest of the app (Steps 1–5) remains the same as your previous working version.
# (Full code for other steps is unchanged – keep them from your last code.)

st.caption("Always consult a healthcare professional. This app is for educational use.")
