import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from collections import defaultdict
import calendar

# ───────── Page Config ─────────
st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 Study Schedule Weekly Planner")

# ───────── Helper: generate full-length exam tasks ─────────
def generate_full_length_tasks():
    tasks = []
    # Weekly full-length exams every Monday from July 7 - August 25
    start_fl = date(2025, 7, 7)
    end_fl = date(2025, 8, 25)
    current = start_fl
    while current <= end_fl:
        tasks.append({
            "Topic": "",  # no extra topic
            "Task Type": "Full Length Exam",
            "Date": current,
        })
        current += timedelta(weeks=1)
    return pd.DataFrame(tasks)

# ───────── Upload Excel File ─────────
uploaded_file = st.file_uploader("Upload your MCAT Study Schedule Excel file", type=["xlsx"])
if not uploaded_file:
    st.info("Please upload an Excel file to continue.")
    st.stop()

# Read the “Master” sheet
xls = pd.ExcelFile(uploaded_file)
df_master = xls.parse("Master")

# Melt to long format
melted = pd.melt(
    df_master,
    id_vars=["Topic"],
    value_vars=[
        "Study Date",
        "1-Day Review",
        "3-Day Review",
        "7-Day Review",
        "14-Day Review",
        "30-Day Review",
        "60-Day Review",
        "Final Review",
    ],
    var_name="Task Type",
    value_name="Date",
)
melted = melted.dropna(subset=["Date"]).copy()
melted["Date"] = pd.to_datetime(melted["Date"]).dt.date

# ───────── Append weekly exams ─────────
generated_fl = generate_full_length_tasks()
if not generated_fl.empty:
    melted = pd.concat([melted, generated_fl], ignore_index=True)

# ───────── Sidebar: All Settings (in Expanders) ─────────
st.sidebar.header("⚙️ Shift & Display Settings")

# --- 1) Conference Settings ---
with st.sidebar.expander("📅 Conference Settings", expanded=False):
    st.write("If you have any conference (busy) date ranges, set how many here. By default, this is zero.")
    n_conf = st.number_input(
        "Number of Conference ranges", min_value=0, max_value=5, value=0, step=1
    )
    conf_ranges = []
    for i in range(int(n_conf)):
        default_start = datetime.today().date()
        default_end = default_start + timedelta(days=1)

        cr = st.date_input(
            f"Conference range {i+1} (start, end):",
            value=(default_start, default_end),
            key=f"conf_range_{i}",
        )
        start_date, end_date = cr if isinstance(cr, tuple) and len(cr)==2 else (default_start, default_end)
        if end_date < start_date:
            st.error(f"End date must be on or after start date for range {i+1}.")
            st.stop()
        conf_ranges.append((start_date, end_date))

    shift_conference_types = st.multiselect(
        "Which Task Types to shift out of Conference days?",
        options=melted['Task Type'].unique().tolist(),
        default=["Study Date"],
        help="Only tasks whose type is checked here will move if they land in any Conference range.",
    )

# --- 2) Vacation Settings ---
with st.sidebar.expander("🏖️ Vacation Settings", expanded=False):
    st.write("If you have any vacation/missed date ranges, set how many here. By default, this is zero.")
    n_vac = st.number_input(
        "Number of Vacation ranges", min_value=0, max_value=5, value=0, step=1
    )
    vac_ranges = []
    for i in range(int(n_vac)):
        default_start = datetime.today().date()
        default_end = default_start + timedelta(days=1)

        vr = st.date_input(
            f"Vacation range {i+1} (start, end):",
            value=(default_start, default_end),
            key=f"vac_range_{i}",
        )
        vac_start, vac_end = vr if isinstance(vr, tuple) and len(vr)==2 else (default_start, default_end)
        if vac_end < vac_start:
            st.error(f"End date must be on or after start date for range {i+1}.")
            st.stop()
        vac_ranges.append((vac_start, vac_end))

    shift_vacation_types = st.multiselect(
        "Which Task Types to redistribute from Vacation days?",
        options=melted['Task Type'].unique().tolist(),
        default=[t for t in melted['Task Type'].unique() if "Review" in t],
        help="Only tasks whose type is checked here will be pulled off any date in vacation ranges and redistributed forward (max 6 tasks/day).",
    )

# --- 3) Display Settings (with Week Navigation) ---
with st.sidebar.expander("🔍 Display Settings", expanded=True):
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = datetime.today().date()

    def go_to_previous_week():
        st.session_state["selected_date"] -= timedelta(days=7)

    def go_to_next_week():
        st.session_state["selected_date"] += timedelta(days=7)

    col1, col2 = st.columns(2)
    with col1:
        st.button("← Previous Week", on_click=go_to_previous_week)
    with col2:
        st.button("Next Week →", on_click=go_to_next_week)

    selected_date = st.date_input(
        "Select a date (to view that week):",
        value=st.session_state["selected_date"],
        key="selected_date",
    )

    display_types = st.multiselect(
        "Show only these Task Types:",
        options=melted['Task Type'].unique().tolist(),
        default=melted['Task Type'].unique().tolist(),
    )
    search_topic = st.text_input("Search Topic")

# ───────── Compute Week Bounds ─────────
week_start = st.session_state["selected_date"] - timedelta(days=st.session_state["selected_date"].weekday())
week_days = [week_start + timedelta(days=i) for i in range(7)]

# ───────── Apply Shifting Logic (unchanged) ─────────
# ... (maintain your existing shifting logic here) ...

# ───────── Filter for Display ─────────
# ... (your existing filtering logic) ...

tasks_by_day = defaultdict(list)
# ... (populate tasks_by_day) ...

# ───────── Render Weekly View ─────────
total_remaining = 0
# ... (calculate total_remaining) ...

# Show total and persistent practice reminder from July 1 onward
st.markdown(f"<h2 style='margin-bottom:10px;'>Total tasks remaining this week: {total_remaining}</h2>", unsafe_allow_html=True)
if st.session_state["selected_date"] >= date(2025, 7, 1):
    st.markdown(
        "<div style='background-color:#e63946; color:white; padding:12px; border-radius:6px; font-size:1.1em; margin-bottom:20px;'>"
        "📖 <strong>Daily Reminder:</strong> Complete 40 Practice Questions every day!"
        "</div>",
        unsafe_allow_html=True,
    )
st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

# ... (render the 7-column calendar as before) ...
