import streamlit as st
import google.generativeai as genai
import os
import tempfile
from datetime import datetime, timedelta
import json

# Configure Gemini API - User needs to provide their own API key
GEMINI_API_KEY = st.sidebar.text_input("Enter your Google Gemini API Key", type="password")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    st.warning("Please enter your Gemini API Key in the sidebar to enable AI suggestions.")

# Session state for progress tracking and flow
if 'progress_data' not in st.session_state:
    st.session_state.progress_data = []
if 'current_exercises' not in st.session_state:
    st.session_state.current_exercises = []
if 'step' not in st.session_state:
    st.session_state.step = 0  # 0: Initial Assessment, 1: Movement Screens, 2: Pain & Safety, 3: Recommendations, 4: Post-Exercise, 5: End
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

st.title("AI Physical Therapy App")
st.write("This app guides you through a structured physical therapy session using Gemini for video analysis. Follow the steps below.")

# Check for weekly reassessment
if st.session_state.step == 0 and st.session_state.progress_data:
    last_entry = st.session_state.progress_data[-1]
    last_date = datetime.strptime(last_entry["date"], "%Y-%m-%d %H:%M")
    if datetime.now() - last_date > timedelta(days=7):
        st.warning("It's time for your weekly reassessment.")
        if st.button("Perform Weekly Reassessment"):
            st.session_state.step = 1
            st.rerun()

# Function to analyze video using Gemini
def analyze_video(video_path, movement_type, variant=None):
    # Upload video to Gemini
    uploaded_file = genai.upload_file(video_path)
    
    # Prepare prompt
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
    - metrics: dict of quantified values (e.g., {'step_count': int, 'asymmetry_hip': float, ...})
    - weak_muscles: list of strings
    - fall_risk: string (low/medium/high)
    """
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt, uploaded_file])
    
    # Parse JSON from response
    try:
        analysis = json.loads(response.text.strip('```json').strip('```'))
    except json.JSONDecodeError:
        st.error("Failed to parse analysis. Raw response: " + response.text)
        return {"weak_muscles": [], "fall_risk": "low", "metrics": {}}
    
    # Clean up uploaded file
    genai.delete_file(uploaded_file.name)
    
    return analysis

# Function to update analysis results
def update_analysis(new_analysis, movement_type):
    for w in new_analysis["weak_muscles"]:
        if w not in st.session_state.analysis_results["weak_muscles"]:
            st.session_state.analysis_results["weak_muscles"].append(w)
    fall_num = {"low": 1, "medium": 2, "high": 3}
    current_fall = st.session_state.analysis_results["fall_risk"]
    if fall_num[new_analysis["fall_risk"]] > fall_num[current_fall]:
        st.session_state.analysis_results["fall_risk"] = new_analysis["fall_risk"]
    st.session_state.analysis_results["metrics"][movement_type] = new_analysis["metrics"]
    st.session_state.performed_movements.add(movement_type)

# Step 0: Initial Assessment
if st.session_state.step == 0:
    st.subheader("Initial Assessment")
    age = st.number_input("Enter your age", min_value=0, max_value=120)
    baseline_pain = st.slider("Baseline pain level (0-10)", 0, 10, 0)
    chief_complaint_type = st.selectbox("Chief complaint", ["Pain", "Balance", "Other"])
    original_complaint = st.text_area("Describe your original complaint or issue")

    if age > 50 or baseline_pain > 4:
        st.warning("Based on your age or pain level, we recommend seated exercises for safety.")
        override = st.checkbox("Override and proceed with standing exercises")
        seated_recommended = not override
    else:
        seated_recommended = False
        override = False

    if st.button("Proceed to Movement Screens"):
        st.session_state.user_data = {
            "age": age,
            "baseline_pain": baseline_pain,
            "chief_complaint_type": chief_complaint_type,
            "original_complaint": original_complaint,
            "seated_recommended": seated_recommended,
            "override": override
        }
        st.session_state.step = 1
        st.rerun()

# Step 1: Movement Screens
elif st.session_state.step == 1:
    st.subheader("Step 1: Movement Screens")
    pain_areas = st.multiselect("Select painful body parts", ["Neck", "Shoulders", "Back", "Hips", "Knees", "Ankles", "Other"])
    other_pain = st.text_input("If 'Other', specify:")
    st.session_state.analysis_results["pain_areas"] = pain_areas + [other_pain] if other_pain else pain_areas

    for pain in st.session_state.analysis_results["pain_areas"]:
        if pain:
            if pain not in st.session_state.analysis_results["weak_muscles"]:
                st.session_state.analysis_results["weak_muscles"].append(f"Pain in {pain} - target surrounding muscles")

    # Walking
    st.subheader("Walking Assessment")
    walking_ability = st.radio("Can you perform walking?", ["Yes - Upload video", "Unable to perform"])
    if walking_ability == "Yes - Upload video":
        uploaded_walking = st.file_uploader("Upload walking video", type=["mp4", "mov", "avi"], key="walking")
        if uploaded_walking and st.button("Analyze Walking") and GEMINI_API_KEY:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_walking.read())
            analysis = analyze_video(tfile.name, "walking")
            update_analysis(analysis, "walking")
            os.remove(tfile.name)
            st.success("Walking analyzed.")
            st.write(analysis["metrics"])

    # Squatting
    st.subheader("Squatting Assessment")
    squat_ability = st.selectbox("Squatting ability", ["Full squat", "Sit to stand from chair", "Unable to perform"])
    if squat_ability != "Unable to perform":
        uploaded_squat = st.file_uploader("Upload squatting video", type=["mp4", "mov", "avi"], key="squat")
        if uploaded_squat and st.button("Analyze Squatting") and GEMINI_API_KEY:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_squat.read())
            analysis = analyze_video(tfile.name, "squatting", variant=squat_ability)
            update_analysis(analysis, "squatting")
            os.remove(tfile.name)
            st.success("Squatting analyzed.")
            st.write(analysis["metrics"])

    # Balance
    st.subheader("Balance Assessment")
    balance_ability = st.selectbox("Balance ability", ["Single leg balance", "Tandem stance", "Wide tandem stance", "Rhomberg stance", "Unable to perform"])
    if balance_ability != "Unable to perform":
        uploaded_balance = st.file_uploader("Upload balance video", type=["mp4", "mov", "avi"], key="balance")
        if uploaded_balance and st.button("Analyze Balance") and GEMINI_API_KEY:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_balance.read())
            analysis = analyze_video(tfile.name, "balance", variant=balance_ability)
            update_analysis(analysis, "balance")
            os.remove(tfile.name)
            st.success("Balance analyzed.")
            st.write(analysis["metrics"])

    st.subheader("Analysis Summary")
    st.write("Weak Muscles:", ", ".join(st.session_state.analysis_results["weak_muscles"]) or "None detected")
    st.write("Fall Risk:", st.session_state.analysis_results["fall_risk"])
    st.write("Metrics:", st.session_state.analysis_results["metrics"])

    if len(st.session_state.performed_movements) > 0:
        if st.button("Proceed to Pain & Safety Checks"):
            st.session_state.step = 2
            st.rerun()
    else:
        st.error("No movements could be assessed. This is a red flag - consult a doctor. Cannot proceed.")
        st.session_state.pain_flags.append("No movements assessed")

# Step 2: Pain & Safety Checks
elif st.session_state.step == 2:
    st.subheader("Step 2: Pain & Safety Checks")
    st.write("Answer these questions to check for red/yellow flags.")

    red_flags = [
        "Do you have sudden severe pain?",
        "Have you experienced unexplained weight loss?",
        "Do you have a history of cancer?",
        "Do you have numbness or tingling in limbs?",
        "Have you had a recent injury or fall?"
    ]
    for flag in red_flags:
        if st.checkbox(flag):
            st.session_state.pain_flags.append(flag)

    if st.session_state.pain_flags:
        st.error("Red/Yellow flags detected. Consult a doctor before proceeding.")
        override_flags = st.checkbox("Override and proceed anyway (not recommended for no movements assessed)")
    else:
        override_flags = True

    warm_up = "Recommended warm-up: 5-10 minutes of light walking or marching in place."
    st.write(warm_up)

    if (override_flags or not st.session_state.pain_flags) and st.button("Proceed to Exercise Recommendations"):
        st.session_state.step = 3
        st.rerun()

# Step 3: AI Exercise Recommendation and Session Flow
elif st.session_state.step == 3:
    st.subheader("Step 3: Daily Session Flow")
    user_data = st.session_state.user_data
    analysis = st.session_state.analysis_results
    seated = user_data["seated_recommended"] and not user_data["override"]

    difficulty_feedback = st.text_area("Feedback on difficulty or pain (optional):")

    add_balance = False
    if analysis["fall_risk"] != "low":
        add_balance = st.checkbox("Add additional exercises to improve balance")

    if user_data["chief_complaint_type"] == "Balance":
        st.info("Focusing on balance exercises since chief complaint is balance.")

    instruction_type = st.selectbox("Select Instructions", ["Text Guide", "Video Demo", "Voice Guide"])
    if instruction_type != "Text Guide":
        st.warning(f"{instruction_type} not implemented in this prototype. Using Text Guide.")

    # Generate exercises if not already
    if not st.session_state.current_exercises and GEMINI_API_KEY and analysis["weak_muscles"]:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        spine_pain = any("back" in p.lower() or "spine" in p.lower() or "neck" in p.lower() for p in analysis["pain_areas"])
        primary_focus = "balance" if user_data["chief_complaint_type"] == "Balance" else ("spine" if spine_pain else "joint")
        
        prompt = f"""
        User data: Age {user_data['age']}, Baseline pain {user_data['baseline_pain']}, Chief complaint type: {user_data['chief_complaint_type']}, Complaint: {user_data['original_complaint']}.
        Movement analysis: weak muscles - {', '.join(analysis['weak_muscles'])}.
        Pain areas: {', '.join(analysis['pain_areas'])}.
        Fall risk: {analysis['fall_risk']}.
        Seated recommended: {seated}.
        Primary focus: {primary_focus} exercises.
        Secondary: based on deficits and fall-risk.
        Suggest exactly 5 appropriate physical therapy exercises.
        Include progressions, regressions for each.
        If seated: provide seated versions.
        For spinal exercises, offer standing or chair versions.
        Feedback: {difficulty_feedback}.
        """
        if add_balance or user_data["chief_complaint_type"] == "Balance":
            prompt += " Include additional balance exercises if fall risk is increased. If chief complaint is balance, focus only on balance exercises."
        prompt += " Format as a list with descriptions."

        response = model.generate_content(prompt)
        exercises = [ex.strip() for ex in response.text.split('\n') if ex.strip()]
        st.session_state.current_exercises = exercises[:5]  # Ensure 5

    warm_up_opt = st.checkbox("Do Warm-Up Exercises (Optional)")
    if warm_up_opt and GEMINI_API_KEY:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = "Suggest 2-3 simple warm-up exercises for a physical therapy session. Format as a list."
        response = model.generate_content(prompt)
        warm_ups = response.text.split('\n')
        st.subheader("Warm-Up Exercises")
        for wu in warm_ups:
            if wu.strip():
                st.write(wu)

    # Exercise loop
    if st.session_state.exercise_index < len(st.session_state.current_exercises):
        index = st.session_state.exercise_index
        ex = st.session_state.current_exercises[index]
        st.subheader(f"Exercise {index + 1} of {len(st.session_state.current_exercises)}")
        st.write(ex)

        if st.button("Performed Exercise"):
            st.session_state.show_rating = True
            st.rerun()

        if st.session_state.show_rating:
            pain_increased = st.radio("Did pain level increase?", ["No", "Yes"])
            difficulty = st.selectbox("Difficulty?", ["Easy", "Just Right", "Hard"])

            if st.button("Submit Rating"):
                st.session_state.exercise_feedbacks.append({
                    "exercise": ex,
                    "pain_increased": pain_increased == "Yes",
                    "difficulty": difficulty
                })
                st.session_state.exercise_index += 1
                st.session_state.show_rating = False
                st.rerun()
    else:
        st.success("All exercises completed.")
        if st.button("Proceed to Post-Exercise Assessment"):
            st.session_state.step = 4
            st.rerun()

# Step 4: Post-Exercise Pain Assessment
elif st.session_state.step == 4:
    st.subheader("Step 4: Post-Session Pain Assessment")
    post_pain = st.slider("Post-session pain level (0-10)", 0, 10, 0)
    pain_response = st.text_area("Describe any pain or issues during the session:")

    if st.button("Store Data and Generate Summary"):
        # Update next day's plan using Gemini
        if GEMINI_API_KEY:
            model = genai.GenerativeModel('gemini-1.5-flash')
            feedbacks_str = "\n".join([f"Exercise: {fb['exercise']}, Pain Increased: {fb['pain_increased']}, Difficulty: {fb['difficulty']}" for fb in st.session_state.exercise_feedbacks])
            prompt = f"""
            Current exercises: {', '.join(st.session_state.current_exercises)}.
            Per-exercise feedbacks: {feedbacks_str}.
            Post-pain: {post_pain}, Response: {pain_response}.
            Update the plan for next day: regress exercises where pain increased or difficulty was easy, keep if just right, progress if hard.
            Suggest updated 5 exercises with descriptions.
            """
            response = model.generate_content(prompt)
            next_exercises = [ex.strip() for ex in response.text.split('\n') if ex.strip()][:5]

            st.subheader("Session Summary")
            st.write("Data saved. Next day's updated plan:")
            for ex in next_exercises:
                st.write(ex)
        else:
            next_exercises = []

        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {
            "date": current_date,
            **st.session_state.analysis_results,
            "post_pain": post_pain,
            "pain_response": pain_response,
            "exercises": st.session_state.current_exercises,
            "exercise_feedbacks": st.session_state.exercise_feedbacks,
            "next_exercises": next_exercises
        }
        st.session_state.progress_data.append(entry)

        # Reset for next session
        st.session_state.exercise_feedbacks = []
        st.session_state.exercise_index = 0
        st.session_state.current_exercises = next_exercises  # Set for next session

        st.session_state.step = 5
        st.rerun()

# Step 5: End Session
elif st.session_state.step == 5:
    st.subheader("Session Ended")
    st.write("Thank you for completing the session. Here's your progress history:")

    for entry in st.session_state.progress_data:
        st.write(f"{entry['date']}: Metrics: {entry['metrics']}")
        st.write("Weak Muscles: " + ", ".join(entry['weak_muscles']))
        st.write(f"Post-Pain: {entry['post_pain']}, Response: {entry['pain_response']}")
        st.write("Exercises: " + ", ".join(entry['exercises']))
        st.write("Next Exercises: " + ", ".join(entry.get('next_exercises', [])))

    if st.button("Start New Session"):
        st.session_state.step = 0
        st.session_state.user_data = {}
        st.session_state.analysis_results = {"weak_muscles": [], "fall_risk": "low", "pain_areas": [], "metrics": {}}
        st.session_state.pain_flags = []
        st.session_state.current_exercises = []
        st.session_state.performed_movements = set()
        st.session_state.exercise_feedbacks = []
        st.session_state.exercise_index = 0
        st.session_state.show_rating = False
        st.rerun()

st.write("Note: This is a prototype app. Consult a professional physical therapist for personalized advice. For mobile use, access via browser and add to home screen.")