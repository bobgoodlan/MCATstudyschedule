import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

# 1) Import the sortable container
from streamlit_sortables import sortables

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
melted["Date"] = pd.to_datetime(melted["Date"]).dt.date  # convert to python date

# ───────── Sidebar: Dynamic Shift Controls ─────────
st.sidebar.header("⚙️ Shift Settings")

# 1) Conference (busy) date range
conf_range = st.sidebar.date_input(
    "Conference (busy) days:",
    value=(datetime(2025, 6, 23).date(), datetime(2025, 6, 25).date()),
    help="Any ‘Study Date’ tasks in this range will be shifted out.",
)
if not (isinstance(conf_range, tuple) and len(conf_range) == 2):
    st.error("Select exactly two dates for the conference range.")
    st.stop()
conf_start, conf_end = conf_range

# 2) Vacation (missed) date range
vac_range = st.sidebar.date_input(
    "Vacation (missed) days:",
    value=(datetime(2025, 5, 31).date(), datetime(2025, 6, 1).date()),
    help="Any review tasks in this range will be redistributed forward (max 6/day).",
)
if not (isinstance(vac_range, tuple) and len(vac_range) == 2):
    st.error("Select exactly two dates for the vacation range.")
    st.stop()
vac_start, vac_end = vac_range

# 3) Which Task Types to shift out of the Conference window?
shift_conference_types = st.sidebar.multiselect(
    "Shift these types out of Conference days:",
    options=melted["Task Type"].unique().tolist(),
    default=["Study Date"],
    help="Only tasks whose type is checked here will move if they land in the Conference range.",
)

# 4) Which Task Types to redistribute from Vacation days?
shift_vacation_types = st.sidebar.multiselect(
    "Redistribute these types from Vacation days:",
    options=melted["Task Type"].unique().tolist(),
    default=[t for t in melted["Task Type"].unique() if "Review" in t],
    help="Only tasks whose type is checked here will be pulled off any date in the Vacation range and redistributed forward (max 6 tasks/day).",
)

# 5) Week selector (Mon–Sun of that week)
selected_date = st.sidebar.date_input(
    "Select a date (to view that week):", value=datetime.today().date()
)
week_start = selected_date - timedelta(days=selected_date.weekday())
week_days = [week_start + timedelta(days=i) for i in range(7)]

# 6) Additional display filters: Task Type + Topic keyword
st.sidebar.markdown("---")
display_types = st.sidebar.multiselect(
    "Show only these Task Types:", options=melted["Task Type"].unique().tolist(),
    default=melted["Task Type"].unique().tolist(),
)
search_topic = st.sidebar.text_input("Search Topic")

# ───────── Apply Shifting Logic ─────────
df_shifted = melted.copy()

# 1) Shift out “Conference” days (only for types in shift_conference_types)
for idx, row in df_shifted.iterrows():
    d = row["Date"]
    t = row["Task Type"]
    if (t in shift_conference_types) and (conf_start <= d <= conf_end):
        while conf_start <= d <= conf_end:
            d = d + timedelta(days=1)
        df_shifted.at[idx, "Date"] = d

# 2) Collect all “Vacation” rows that need redistribution
vac_indices = []
for idx, row in df_shifted.iterrows():
    d = row["Date"]
    t = row["Task Type"]
    if (t in shift_vacation_types) and (vac_start <= d <= vac_end):
        vac_indices.append(idx)

# Build a count of “occupied slots” on each day AFTER vac_end
slot_counts = defaultdict(int)
for idx, row in df_shifted.iterrows():
    d = row["Date"]
    if d > vac_end:
        slot_counts[d] += 1

# Redistribute each “vacation” task to the earliest date > vac_end where slot < 6
for idx in sorted(vac_indices, key=lambda i: df_shifted.at[i, "Date"]):
    candidate = vac_end + timedelta(days=1)
    while slot_counts[candidate] >= 6:
        candidate += timedelta(days=1)
    df_shifted.at[idx, "Date"] = candidate
    slot_counts[candidate] += 1

# 3) Avoid collisions among “Study Date” (if “Study Date” in shift_conference_types)
if "Study Date" in shift_conference_types:
    study_rows = df_shifted[df_shifted["Task Type"] == "Study Date"].copy()
    occupied = set()
    for idx, row in study_rows.sort_values("Date").iterrows():
        d = row["Date"]
        if d not in occupied:
            occupied.add(d)
        else:
            candidate = d + timedelta(days=1)
            while (candidate in occupied) or (conf_start <= candidate <= conf_end):
                candidate += timedelta(days=1)
            df_shifted.at[idx, "Date"] = candidate
            occupied.add(candidate)

# ───────── Filter & Prepare for Drag/Drop Rendering ─────────
# A) Filter by “display_types” and “search_topic”
filtered = df_shifted[df_shifted["Task Type"].isin(display_types)].copy()
if search_topic:
    filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

# B) Group into a dict: { date → list of (task_type, topic, original_index) }
tasks_by_day = defaultdict(list)
for _, row in filtered.iterrows():
    tasks_by_day[row["Date"]].append((row["Task Type"], row["Topic"], str(_)))  
    # we keep the original row‐index (as string) so we can track it after drag/drop

# C) Compute total tasks in this week
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

# ───────── Prepare initial lists of “draggable items” ─────────
#
# Each “item” in streamlit-sortables must be a string. We’ll encode:
#    "<task_type>︱<topic>︱<orig_index>"
# Then after drag/drop we’ll parse out orig_index to update df_shifted.

initial_lists = []
for day in week_days:
    day_items = tasks_by_day.get(day, [])
    coded = [f"{t}︱{topic}︱{idx}" for (t, topic, idx) in day_items]
    initial_lists.append(coded)

# ───────── Drag/Drop Component ─────────
#
# The call to `sortables` returns a list of 7 lists (one per container),
# with the same “string‐encoded items” but in the new order/container.
#
# We use direction="horizontal" so the user sees 7 side‐by‐side lists that they can drag between.
updated_lists = sortables(
    label="**🔀 Drag & drop tasks between days** (within this week):",
    items_list=initial_lists,
    keys=[f"col_{i}" for i in range(7)],
    direction="horizontal",
    container_css=""" 
        width: 130px; 
        min-height: 200px; 
        background-color: #f0f0f0; 
        padding: 6px; 
        border-radius: 8px; 
        margin-right: 8px;
    """,
    item_css="""
        padding: 6px 8px;
        margin: 4px 0;
        background-color: white;
        border: 1px solid #ccc;
        border-radius: 4px;
        cursor: grab;
    """,
)

# If the user moved anything, `updated_lists` will be a non‐None list of 7 sub‐lists.
# We now parse those strings back to (orig_index) and update df_shifted["Date"].
if updated_lists is not None:
    # Build a reverse map: for each orig_index, which new day it belongs to
    for col_idx, new_list in enumerate(updated_lists):
        new_date = week_days[col_idx]
        for coded in new_list:
            # coded = "<task_type>︱<topic>︱<orig_index>"
            try:
                parts = coded.split("︱")
                orig_idx = int(parts[-1])
                # Overwrite the Date in df_shifted for that row
                df_shifted.at[orig_idx, "Date"] = new_date
            except:
                continue

    # After reassigning df_shifted dates, we should re‐compute the “filtered” and “tasks_by_day”
    # so that the rest of the UI (like “Total tasks this week”) updates instantly.
    filtered = df_shifted[df_shifted["Task Type"].isin(display_types)].copy()
    if search_topic:
        filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]
    # Re‐group
    tasks_by_day = defaultdict(list)
    for _, row in filtered.iterrows():
        tasks_by_day[row["Date"]].append((row["Task Type"], row["Topic"], str(_)))
    total_tasks_this_week = sum(len(tasks_by_day.get(day, [])) for day in week_days)

# ───────── Render the Weekly View (post–drag/drop update) ─────────
st.markdown(f"<h2 style='margin-bottom:20px;'>Total tasks this week: {total_tasks_this_week}</h2>", unsafe_allow_html=True)
st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

cols = st.columns(7)
for i, day in enumerate(week_days):
    with cols[i]:
        # Day header
        st.markdown(
            f"<div style='margin-bottom:16px;'>"
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
            for idx, (task_type, topic, orig_idx) in enumerate(day_tasks):
                key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                color = color_map.get(task_type, "#000000")

                with st.container():
                    # 1) Checkbox
                    st.checkbox("", key=key)
                    # 2) Colored pill
                    pill_html = (
                        f"<div style='display:inline-block; "
                        f"background-color:{color}; color:white; "
                        f"padding:4px 8px; border-radius:4px; "
                        f"font-size:0.9em; font-weight:500; "
                        f"margin-left:6px; margin-bottom:4px;'>"
                        f"{task_type}</div>"
                    )
                    st.markdown(pill_html, unsafe_allow_html=True)
                    # 3) Topic text
                    topic_html = (
                        f"<div style='margin-left:12px; font-size:0.9em; color:#e0e0e0; "
                        f"margin-bottom:12px;'>"
                        f"{topic}</div>"
                    )
                    st.markdown(topic_html, unsafe_allow_html=True)

# ───────── Optional: Show Raw Data Table ─────────
with st.expander("📋 View Data Table"):
    st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))
