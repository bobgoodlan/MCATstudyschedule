import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from collections import defaultdict
import calendar

# ───────── Page Config ─────────
st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 Study Schedule Weekly Planner")

# ───────── Helper: generate additional tasks ─────────
def generate_tasks():
    tasks = []
    # 1) Daily practice questions from UWORLD: 40 questions/day from July 30 - August 31
    start_practice = date(2025, 7, 30)
    end_practice = date(2025, 8, 31)
    current = start_practice
    while current <= end_practice:
        tasks.append({
            "Topic": "UWORLD - mixed subjects (40 questions)",
            "Task Type": "Practice Questions",
            "Date": current,
        })
        current += timedelta(days=1)

    # 2) Weekly full-length exams every Monday from July 7 - August 25
    start_fl = date(2025, 7, 7)
    end_fl = date(2025, 8, 25)
    current = start_fl
    while current <= end_fl:
        tasks.append({
            "Topic": "Full Length MCAT Exam",  
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

# ───────── Append generated tasks ─────────
generated = generate_tasks()
# Ensure correct dtypes
if not generated.empty:
    generated["Date"] = pd.to_datetime(generated["Date"]).dt.date
    # Append to our melted schedule
    melted = pd.concat([melted, generated], ignore_index=True)

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
        if not isinstance(cr, tuple) or len(cr) != 2:
            st.error(f"Select exactly two dates for Conference range {i+1}.")
            st.stop()

        start_date, end_date = cr
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
        if not isinstance(vr, tuple) or len(vr) != 2:
            st.error(f"Select exactly two dates for Vacation range {i+1}.")
            st.stop()

        vac_start, vac_end = vr
        if vac_end < vac_start:
            st.error(f"End date must be on or after start date for range {i+1}.")
            st.stop()

        vac_ranges.append((vac_start, vac_end))

    shift_vacation_types = st.multiselect(
        "Which Task Types to redistribute from Vacation days?",
        options=melted["Task Type"].unique().tolist(),
        default=[t for t in melted["Task Type"].unique() if "Review" in t],
        help="Only tasks whose type is checked here will be pulled off any date in vacation ranges and redistributed forward (max 6 tasks/day).",
    )

# --- 3) Display Settings (with Week Navigation) ---
with st.sidebar.expander("🔍 Display Settings", expanded=True):
    # Initialize session_state for selected_date if not already present
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = datetime.today().date()

    # Callback functions for Prev/Next Week
    def go_to_previous_week():
        st.session_state["selected_date"] -= timedelta(days=7)

    def go_to_next_week():
        st.session_state["selected_date"] += timedelta(days=7)

    col1, col2 = st.columns([1, 1])
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
        options=melted["Task Type"].unique().tolist(),
        default=melted["Task Type"].unique().tolist(),
    )
    search_topic = st.text_input("Search Topic")


# ───────── Compute Week Bounds ─────────
week_start = selected_date - timedelta(days=selected_date.weekday())
week_days = [week_start + timedelta(days=i) for i in range(7)]


# ───────── Apply Shifting Logic ─────────
df_shifted = melted.copy()

def in_any_range(date_obj, ranges_list):
    """Return True if date_obj is in any of the (start, end) pairs in ranges_list."""
    for start, end in ranges_list:
        if start <= date_obj <= end:
            return True
    return False

# 1) Shift out of all Conference ranges (if any)
for idx, row in df_shifted.iterrows():
    orig_date = row["Date"]
    ttype = row["Task Type"]
    if (ttype in shift_conference_types) and in_any_range(orig_date, conf_ranges):
        d = orig_date
        # Keep shifting forward until date is no longer in any conf_range
        while in_any_range(d, conf_ranges):
            d += timedelta(days=1)
        df_shifted.at[idx, "Date"] = d

# 2) Redistribute each Vacation range, one by one (if any)
vac_ranges_sorted = sorted(vac_ranges, key=lambda x: x[0])
for vr_start, vr_end in vac_ranges_sorted:
    # 2a) Find all indices that fall in this vacation window
    vac_indices = []
    for idx, row in df_shifted.iterrows():
        d = row["Date"]
        ttype = row["Task Type"]
        if (ttype in shift_vacation_types) and (vr_start <= d <= vr_end):
            vac_indices.append(idx)

    # 2b) Count “occupied slots” for every date > vr_end
    slot_counts = defaultdict(int)
    for idx2, row2 in df_shifted.iterrows():
        d2 = row2["Date"]
        if d2 > vr_end:
            slot_counts[d2] += 1

    # 2c) Re‐assign each vac_index to the first date > vr_end with < 6 tasks and not in a conference range
    for idx in sorted(vac_indices, key=lambda i: df_shifted.at[i, "Date"]):
        candidate = vr_end + timedelta(days=1)
        while slot_counts[candidate] >= 6 or in_any_range(candidate, conf_ranges):
            candidate += timedelta(days=1)
        df_shifted.at[idx, "Date"] = candidate
        slot_counts[candidate] += 1

# 3) Avoid collisions among “Study Date” if that type was in shift_conference_types
if "Study Date" in shift_conference_types:
    study_rows = df_shifted[df_shifted["Task Type"] == "Study Date"].copy()
    occupied = set()
    for idx, row in study_rows.sort_values("Date").iterrows():
        d = row["Date"]
        if (d not in occupied) and not in_any_range(d, conf_ranges):
            occupied.add(d)
        else:
            candidate = d + timedelta(days=1)
            while (candidate in occupied) or in_any_range(candidate, conf_ranges):
                candidate += timedelta(days=1)
            df_shifted.at[idx, "Date"] = candidate
            occupied.add(candidate)


# ───────── Filtered DataFrame for Display ─────────
filtered = df_shifted[df_shifted["Task Type"].isin(display_types)].copy()
if search_topic:
    filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

tasks_by_day = defaultdict(list)
for _, row in filtered.iterrows():
    tasks_by_day[row["Date"]].append((row["Task Type"], row["Topic"]))


# ───────── Helper: Clear All Completions This Week ─────────
if st.button("🧹 Clear Completions for This Week"):
    for day in week_days:
        day_tasks = tasks_by_day.get(day, [])
        for idx, (ttype, topic) in enumerate(day_tasks):
            key = f"cb_{day.isoformat()}_{ttype}_{topic}_{idx}"
            if key in st.session_state:
                st.session_state[key] = False
    st.experimental_rerun()


# ───────── Color Map for Task Types ─────────
color_map = {
    "Study Date":    "#1f77b4",
    "1-Day Review":  "#ff7f0e",
    "3-Day Review":  "#2ca02c",
    "7-Day Review":  "#d62728",
    "14-Day Review": "#9467bd",
    "30-Day Review": "#8c564b",
    "60-Day Review": "#e377c2",
    "Final Review":  "#7f7f7f",
}


# ───────── Render the Weekly View ─────────
total_remaining = 0

for day in week_days:
    day_tasks = tasks_by_day.get(day, [])
    for idx, (ttype, topic) in enumerate(day_tasks):
        key = f"cb_{day.isoformat()}_{ttype}_{topic}_{idx}"
        completed = st.session_state.get(key, False)
        if not completed:
            total_remaining += 1

# 1) Header: Total tasks remaining
st.markdown(
    f"<h2 style='margin-bottom:10px;'>Total tasks remaining this week: {total_remaining}</h2>",
    unsafe_allow_html=True,
)
st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

if total_remaining == 0:
    st.info("🎉 All tasks for this week are completed!")

# 2) Draw 7‐column grid for each day
cols = st.columns(7)
for i, day in enumerate(week_days):
    with cols[i]:
        st.markdown(
            f"<div style='margin-bottom:12px;'>"
            f"<strong>{calendar.day_name[day.weekday()]}</strong><br>"
            f"{day.strftime('%b %d')}</div>",
            unsafe_allow_html=True,
        )

        day_tasks = tasks_by_day.get(day, [])
        if not day_tasks:
            st.markdown(
                "<div style='color:gray; font-style:italic; margin-bottom:12px;'>"
                "No tasks</div>",
                unsafe_allow_html=True,
            )
        else:
            for idx, (task_type, topic) in enumerate(day_tasks):
                key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                completed = st.checkbox("", key=key)

                color = color_map.get(task_type, "#000000")
                if not completed:
                    # Normal rendering
                    pill_html = (
                        f"<div style='display:inline-block; "
                        f"background-color:{color}; color:white; "
                        f"padding:4px 8px; border-radius:4px; "
                        f"font-size:0.9em; font-weight:500; "
                        f"margin-left:6px; margin-bottom:4px;'>"
                        f"{task_type}</div>"
                    )
                    st.markdown(pill_html, unsafe_allow_html=True)

                    topic_html = (
                        f"<div style='margin-left:12px; font-size:0.9em; color:#e0e0e0; "
                        f"margin-bottom:12px;'>"
                        f"{topic}</div>"
                    )
                    st.markdown(topic_html, unsafe_allow_html=True)
                else:
                    # Strikethrough & gray for completed
                    pill_html = (
                        f"<div style='display:inline-block; "
                        f"background-color:lightgray; color:#666666; "
                        f"padding:4px 8px; border-radius:4px; "
                        f"font-size:0.9em; font-weight:500; "
                        f"margin-left:6px; margin-bottom:4px; text-decoration: line-through;'>"
                        f"{task_type}</div>"
                    )
                    st.markdown(pill_html, unsafe_allow_html=True)

                    topic_html = (
                        f"<div style='margin-left:12px; font-size:0.9em; color:#999999; "
                        f"margin-bottom:12px; text-decoration: line-through;'>"
                        f"{topic}</div>"
                    )
                    st.markdown(topic_html, unsafe_allow_html=True)


# ───────── Optional: Show Raw Data Table ─────────
with st.expander("📋 View Raw Shifted Data Table"):
    st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))
