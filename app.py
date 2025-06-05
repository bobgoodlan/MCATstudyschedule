import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

# ───────── Page Config ─────────
st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 Study Schedule Weekly Planner")


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


# ───────── Sidebar: All Settings (in Expanders) ─────────
st.sidebar.header("⚙️ Shift & Display Settings")

# --- 1) Conference Settings ---
with st.sidebar.expander("📅 Conference Settings", expanded=False):
    st.write("You can add multiple conference date ranges here. Any checked ‘Task Type’ falling in these ranges will be pushed forward.")
    n_conf = st.number_input(
        "Number of Conference ranges", min_value=1, max_value=5, value=1, step=1
    )
    conf_ranges = []
    for i in range(int(n_conf)):
        cr = st.date_input(
            f"Conference range {i+1}:",
            value=(datetime(2025, 6, 23).date(), datetime(2025, 6, 25).date()),
            key=f"conf_range_{i}",
        )
        if not (isinstance(cr, tuple) and len(cr) == 2):
            st.error(f"Select exactly two dates for conference range {i+1}.")
            st.stop()
        conf_ranges.append(cr)

    shift_conference_types = st.multiselect(
        "Which Task Types to shift out of Conference days?",
        options=melted["Task Type"].unique().tolist(),
        default=["Study Date"],
        help="Only tasks whose type is checked here will move if they land in any Conference range.",
    )

# --- 2) Vacation Settings ---
with st.sidebar.expander("🏖️ Vacation Settings", expanded=False):
    st.write("You can add multiple vacation date ranges here. Checked ‘Task Types’ in these ranges will be redistributed forward (max 6/day).")
    n_vac = st.number_input(
        "Number of Vacation ranges", min_value=1, max_value=5, value=1, step=1
    )
    vac_ranges = []
    for i in range(int(n_vac)):
        vr = st.date_input(
            f"Vacation range {i+1}:",
            value=(datetime(2025, 5, 31).date(), datetime(2025, 6, 1).date()),
            key=f"vac_range_{i}",
        )
        if not (isinstance(vr, tuple) and len(vr) == 2):
            st.error(f"Select exactly two dates for vacation range {i+1}.")
            st.stop()
        vac_ranges.append(vr)

    shift_vacation_types = st.multiselect(
        "Which Task Types to redistribute from Vacation days?",
        options=melted["Task Type"].unique().tolist(),
        default=[t for t in melted["Task Type"].unique() if "Review" in t],
        help="Only tasks whose type is checked here will be pulled off any date in vacation ranges and redistributed forward (max 6 tasks/day).",
    )

# --- 3) Display Settings ---
with st.sidebar.expander("🔍 Display Settings", expanded=True):
    # Week selector + prev/next buttons
    selected_date = st.date_input(
        "Select a date (to view that week):", value=datetime.today().date()
    )
    # Prev / Next Week Buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("← Previous Week"):
            selected_date = selected_date - timedelta(days=7)
            # force rerun with a new key
            st.experimental_rerun()
    with col2:
        if st.button("Next Week →"):
            selected_date = selected_date + timedelta(days=7)
            st.experimental_rerun()

    # Filters: Task Type + Topic keyword
    display_types = st.multiselect(
        "Show only these Task Types:",
        options=melted["Task Type"].unique().tolist(),
        default=melted["Task Type"].unique().tolist(),
    )
    search_topic = st.text_input("Search Topic")


# Compute the week (Monday → Sunday) that contains `selected_date`
week_start = selected_date - timedelta(days=selected_date.weekday())
week_days = [week_start + timedelta(days=i) for i in range(7)]


# ───────── Apply Shifting Logic ─────────
df_shifted = melted.copy()

# 1) Shift out of all Conference ranges (only for selected types)
def in_any_conf_range(date_obj, conf_list):
    for start, end in conf_list:
        if start <= date_obj <= end:
            return True
    return False

for idx, row in df_shifted.iterrows():
    orig_date = row["Date"]
    ttype = row["Task Type"]
    if (ttype in shift_conference_types) and in_any_conf_range(orig_date, conf_ranges):
        d = orig_date
        # Push until no longer in any conf range
        while in_any_conf_range(d, conf_ranges):
            d = d + timedelta(days=1)
        df_shifted.at[idx, "Date"] = d

# 2) Redistribute each Vacation range in chronological order
#    (max 6 tasks per day, only for selected types)
# Sort vac_ranges by start date to process earliest first
vac_ranges_sorted = sorted(vac_ranges, key=lambda x: x[0])

for vr in vac_ranges_sorted:
    vr_start, vr_end = vr
    # 2a) Identify tasks in THIS vacation range that need to be moved
    vac_indices = []
    for idx, row in df_shifted.iterrows():
        d = row["Date"]
        ttype = row["Task Type"]
        if (ttype in shift_vacation_types) and (vr_start <= d <= vr_end):
            vac_indices.append(idx)

    # 2b) Build a fresh count of “occupied slots” for dates AFTER vr_end
    slot_counts = defaultdict(int)
    for idx2, row2 in df_shifted.iterrows():
        d2 = row2["Date"]
        if d2 > vr_end:
            slot_counts[d2] += 1

    # 2c) Redistribute each “vacation” task for THIS range
    for idx in sorted(vac_indices, key=lambda i: df_shifted.at[i, "Date"]):
        candidate = vr_end + timedelta(days=1)
        while slot_counts[candidate] >= 6 or in_any_conf_range(candidate, conf_ranges):
            candidate += timedelta(days=1)
        df_shifted.at[idx, "Date"] = candidate
        slot_counts[candidate] += 1


# 3) Avoid collisions among “Study Date” (only if “Study Date” was in shift_conference_types)
if "Study Date" in shift_conference_types:
    study_rows = df_shifted[df_shifted["Task Type"] == "Study Date"].copy()
    occupied = set()
    for idx, row in study_rows.sort_values("Date").iterrows():
        d = row["Date"]
        if d not in occupied and not in_any_conf_range(d, conf_ranges):
            occupied.add(d)
        else:
            candidate = d + timedelta(days=1)
            while (candidate in occupied) or in_any_conf_range(candidate, conf_ranges):
                candidate += timedelta(days=1)
            df_shifted.at[idx, "Date"] = candidate
            occupied.add(candidate)


# ───────── Filtered DataFrame for Display ─────────
filtered = df_shifted[df_shifted["Task Type"].isin(display_types)].copy()
if search_topic:
    filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

# Group tasks by date (for the entire dataset, but we'll only render the selected week)
tasks_by_day = defaultdict(list)
for _, row in filtered.iterrows():
    tasks_by_day[row["Date"]].append((row["Task Type"], row["Topic"]))


# ───────── Helper: Reset All Completions for Current Week ─────────
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
# 1) First, compute how many tasks remain (unchecked) in this week
remaining_by_type = defaultdict(int)
total_remaining = 0

for day in week_days:
    day_tasks = tasks_by_day.get(day, [])
    for idx, (ttype, topic) in enumerate(day_tasks):
        key = f"cb_{day.isoformat()}_{ttype}_{topic}_{idx}"
        completed = st.session_state.get(key, False)
        if not completed:
            remaining_by_type[ttype] += 1
            total_remaining += 1

# 2) Display the header
st.markdown(
    f"<h2 style='margin-bottom:10px;'>Total tasks remaining this week: {total_remaining}</h2>",
    unsafe_allow_html=True,
)
st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

# 3) Show a per-Type count table (only for types that have >0)
if total_remaining > 0:
    cnt_cols = st.columns(len(remaining_by_type))
    for (ttype, cnt), col in zip(remaining_by_type.items(), cnt_cols):
        with col:
            st.markdown(
                f"<div style='background-color:{color_map.get(ttype,'#cccccc')}; "
                f"color:white; padding:8px; border-radius:4px; text-align:center;'>"
                f"<strong>{ttype}</strong><br>{cnt} left</div>",
                unsafe_allow_html=True,
            )
else:
    st.info("🎉 All tasks for this week are completed!")

# 4) Render each day in a 7‐column grid
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
            st.markdown(
                "<div style='color:gray; font-style:italic; margin-bottom:12px;'>"
                "No tasks</div>",
                unsafe_allow_html=True,
            )
        else:
            # For each task: show checkbox + pill + topic. If checked, render with strikethrough & gray.
            for idx, (task_type, topic) in enumerate(day_tasks):
                key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                # The checkbox itself; default=False if not in session_state
                completed = st.checkbox("", key=key)

                color = color_map.get(task_type, "#000000")
                if not completed:
                    # Normal pill & topic
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
                    # Strikethrough + gray for completed tasks
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
