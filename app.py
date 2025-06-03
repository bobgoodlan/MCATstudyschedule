import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 Study Schedule Weekly Planner")

# ───────── Upload Excel File ─────────
uploaded_file = st.file_uploader("Upload your MCAT Study Schedule Excel file", type=["xlsx"])

if not uploaded_file:
    st.info("Please upload an Excel file to continue.")
    st.stop()

# ─────── Read & Melt to Long Format ───────
xls = pd.ExcelFile(uploaded_file)
df_master = xls.parse("Master")

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
melted["Date"] = pd.to_datetime(melted["Date"]).dt.date  # convert to plain date

# ───────── Sidebar: Set Up Dynamic Ranges & Task Filters ─────────
st.sidebar.header("⚙️ Shift Settings")

# 1) Conference date range (default to June 23–25, 2025)
conf_range = st.sidebar.date_input(
    "Conference (busy) days:",
    value=(datetime(2025, 6, 23).date(), datetime(2025, 6, 25).date()),
    help="Any ‘Study Date’ tasks in this range will be shifted out.",
)
# Ensure we always have exactly two dates: a start and an end
if isinstance(conf_range, tuple) and len(conf_range) == 2:
    conf_start, conf_end = conf_range
else:
    st.error("Please choose exactly two dates for your conference range.")
    st.stop()

# 2) Missed-days (e.g. vacation) date range (default to May 31–June 1, 2025)
vac_range = st.sidebar.date_input(
    "Missed days (vacation):",
    value=(datetime(2025, 5, 31).date(), datetime(2025, 6, 1).date()),
    help="Any review tasks in this range will be shifted forward.",
)
if isinstance(vac_range, tuple) and len(vac_range) == 2:
    vac_start, vac_end = vac_range
else:
    st.error("Please choose exactly two dates for your missed-days range.")
    st.stop()

# 3) Which task types to shift for each range
st.sidebar.markdown("**Select which task types to shift**")
shift_study_types = st.sidebar.multiselect(
    "Shift these task types out of Conference days:",
    options=["Study Date", "1-Day Review", "3-Day Review", "7-Day Review",
             "14-Day Review", "30-Day Review", "60-Day Review", "Final Review"],
    default=["Study Date"],
    help="Only the tasks you check here will move if they land in the Conference range.",
)
shift_review_types = st.sidebar.multiselect(
    "Shift these task types out of Missed days:",
    options=["Study Date", "1-Day Review", "3-Day Review", "7-Day Review",
             "14-Day Review", "30-Day Review", "60-Day Review", "Final Review"],
    default=["1-Day Review", "3-Day Review", "7-Day Review", "14-Day Review"
             ],  # default reviews
    help="Only the tasks you check here will move if they land in the Missed-days range.",
)

# 4) Date to view that week (Mon–Sun)
selected_date = st.sidebar.date_input(
    "Select a date (to view that week):", value=datetime.today().date()
)
week_start = selected_date - timedelta(days=selected_date.weekday())
week_days = [week_start + timedelta(days=i) for i in range(7)]

# 5) Additional filters: Task Type + Topic Search
st.sidebar.markdown("---")
filter_types = st.sidebar.multiselect(
    "Show only these Task Types:", options=melted["Task Type"].unique().tolist(),
    default=melted["Task Type"].unique().tolist(),
)
search_topic = st.sidebar.text_input("Search Topic")

# ───────── Shifting Logic ─────────
# We’ll build a new DataFrame “df_shifted” in which we apply the two shifts:
#  - Any row whose Task Type is in shift_study_types AND date ∈ [conf_start, conf_end]
#      → keep adding +1 day until date > conf_end
#  - Any row whose Task Type is in shift_review_types AND date ∈ [vac_start, vac_end]
#      → keep adding +1 day until date > vac_end
#
# After that, we must also ensure no two “Study Date” tasks collide on the same day.

df_shifted = melted.copy()

# 1) Shift Conference tasks (loop until out of range)
for idx, row in df_shifted.iterrows():
    d = row["Date"]
    t = row["Task Type"]
    if (t in shift_study_types) and (conf_start <= d <= conf_end):
        while conf_start <= d <= conf_end:
            d = d + timedelta(days=1)
        df_shifted.at[idx, "Date"] = d

# 2) Shift Missed-days tasks
for idx, row in df_shifted.iterrows():
    d = row["Date"]
    t = row["Task Type"]
    if (t in shift_review_types) and (vac_start <= d <= vac_end):
        while vac_start <= d <= vac_end:
            d = d + timedelta(days=1)
        df_shifted.at[idx, "Date"] = d

# 3) Prevent collisions among “Study Date” (only if “Study Date” was in shift_study_types)
if "Study Date" in shift_study_types:
    study_rows = df_shifted[df_shifted["Task Type"] == "Study Date"].copy()
    occupied = set()
    for idx, row in study_rows.sort_values("Date").iterrows():
        d = row["Date"]
        # If date is free, occupy; otherwise bump forward until free and not in conf range
        if d not in occupied:
            occupied.add(d)
        else:
            candidate = d + timedelta(days=1)
            while (candidate in occupied) or (conf_start <= candidate <= conf_end):
                candidate += timedelta(days=1)
            df_shifted.at[idx, "Date"] = candidate
            occupied.add(candidate)

# ───────── Filtering & Grouping for Display ─────────
# 1) Apply the Task-Type and Topic filters
filtered = df_shifted[df_shifted["Task Type"].isin(filter_types)].copy()
if search_topic:
    filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

# 2) Group by date → list of (task_type, topic)
tasks_by_day = defaultdict(list)
for _, row in filtered.iterrows():
    tasks_by_day[row["Date"]].append((row["Task Type"], row["Topic"]))

# 3) Compute total tasks in this week
total_tasks_this_week = sum(len(tasks_by_day.get(day, [])) for day in week_days)

# ───────── Color Map for Task Types ─────────
color_map = {
    "Study Date":    "#1f77b4",  # blue
    "1-Day Review":  "#ff7f0e",  # orange
    "3-Day Review":  "#2ca02c",  # green
    "7-Day Review":  "#d62728",  # red
    "14-Day Review": "#9467bd",  # purple
    "30-Day Review": "#8c564b",  # brown
    "60-Day Review": "#e377c2",  # pink
    "Final Review":  "#7f7f7f",  # gray
}

# ───────── Render the Weekly View ─────────
st.markdown(f"<h2>Total tasks this week: {total_tasks_this_week}</h2>", unsafe_allow_html=True)
st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

cols = st.columns(7)
for i, day in enumerate(week_days):
    with cols[i]:
        # Day header
        st.markdown(
            f"<div style='margin-bottom:12px;'>"
            f"<strong>{calendar.day_name[day.weekday()]}</strong><br>"
            f"{day.strftime('%b %d')}</div>",
            unsafe_allow_html=True,
        )

        day_tasks = tasks_by_day.get(day, [])
        if not day_tasks:
            st.markdown("<div style='color:gray; font-style:italic;'>No tasks</div>", unsafe_allow_html=True)
        else:
            # For each task: checkbox + inline pill + topic on a single line
            for idx, (task_type, topic) in enumerate(day_tasks):
                key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                color = color_map.get(task_type, "#000000")
                cb_col, content_col = st.columns([1, 11])
                with cb_col:
                    st.checkbox("", key=key)
                with content_col:
                    st.markdown(
                        f"<span style='background-color:{color}; "
                        f"color:white; padding:4px 8px; border-radius:4px; "
                        f"font-size:0.9em; font-weight:500;'>"
                        f"{task_type}</span>&nbsp;"
                        f"<span style='font-size:0.9em; color:#e0e0e0;'>{topic}</span>",
                        unsafe_allow_html=True,
                    )

# ───────── Optional: Show the Raw Data Table ─────────
with st.expander("📋 View Data Table"):
    st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))
