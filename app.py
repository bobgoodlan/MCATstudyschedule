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
    start_fl = date(2025, 7, 7)
    end_fl = date(2025, 8, 25)
    current = start_fl
    while current <= end_fl:
        tasks.append({
            "Topic": "",
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

# ───────── Append full-length exam tasks ─────────
generated_fl = generate_full_length_tasks()
if not generated_fl.empty:
    melted = pd.concat([melted, generated_fl], ignore_index=True)

# ───────── Fixed Conference Settings ─────────
# Conference dates locked to June 23-25; only shift "Study Date" tasks
conf_ranges = [(date(2025, 6, 23), date(2025, 6, 25))]
shift_conference_types = ["Study Date"]

# ───────── Sidebar: Vacation & Display Settings ─────────
st.sidebar.header("⚙️ Shift & Display Settings")

# Vacation Settings
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
        if isinstance(vr, tuple) and len(vr) == 2:
            vac_start, vac_end = vr
        else:
            vac_start, vac_end = default_start, default_end
        if vac_end < vac_start:
            st.error(f"End date must be on or after start date for range {i+1}.")
            st.stop()
        vac_ranges.append((vac_start, vac_end))
    shift_vacation_types = st.multiselect(
        "Which Task Types to redistribute from Vacation days?",
        options=melted["Task Type"].unique().tolist(),
        default=[t for t in melted["Task Type"].unique() if "Review" in t],
        help="Only tasks whose type is checked here will be redistributed forward (max 6 tasks/day).",
    )

# Display Settings (Week Navigation & Filters)
with st.sidebar.expander("🔍 Display Settings", expanded=True):
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = datetime.today().date()
    def go_prev():
        st.session_state["selected_date"] -= timedelta(days=7)
    def go_next():
        st.session_state["selected_date"] += timedelta(days=7)
    c1, c2 = st.columns(2)
    with c1:
        st.button("← Previous Week", on_click=go_prev)
    with c2:
        st.button("Next Week →", on_click=go_next)
    selected_date = st.date_input(
        "Select a date (to view that week):",
        value=st.session_state["selected_date"], key="selected_date"
    )
    display_types = st.multiselect(
        "Show only these Task Types:",
        options=melted["Task Type"].unique().tolist(),
        default=melted["Task Type"].unique().tolist(),
    )
    search_topic = st.text_input("Search Topic")

# ───────── Compute Week Bounds ─────────
week_start = st.session_state["selected_date"] - timedelta(days=st.session_state["selected_date"].weekday())
week_days = [week_start + timedelta(days=i) for i in range(7)]

# ───────── Apply Shifting Logic ─────────
df_shifted = melted.copy()

def in_any_range(d, ranges):
    return any(start <= d <= end for start, end in ranges)

# Shift out of conference
for idx, row in df_shifted.iterrows():
    d, t = row["Date"], row["Task Type"]
    if t in shift_conference_types and in_any_range(d, conf_ranges):
        while in_any_range(d, conf_ranges):
            d += timedelta(days=1)
        df_shifted.at[idx, "Date"] = d

# Redistribute vacation
vac_ranges_sorted = sorted(vac_ranges, key=lambda x: x[0])
for vr_start, vr_end in vac_ranges_sorted:
    vac_idxs = [i for i, r in df_shifted.iterrows() if r["Task Type"] in shift_vacation_types and vr_start <= r["Date"] <= vr_end]
    slot_counts = defaultdict(int)
    for _, r in df_shifted.iterrows():
        if r["Date"] > vr_end:
            slot_counts[r["Date"]] += 1
    for i in sorted(vac_idxs, key=lambda x: df_shifted.at[x, "Date"]):
        cand = vr_end + timedelta(days=1)
        while slot_counts[cand] >= 6 or in_any_range(cand, conf_ranges):
            cand += timedelta(days=1)
        df_shifted.at[i, "Date"] = cand
        slot_counts[cand] += 1

# Avoid collisions for Study Date
if "Study Date" in shift_conference_types:
    occupied = set()
    for idx, r in df_shifted[df_shifted["Task Type"] == "Study Date"].sort_values("Date").iterrows():
        d = r["Date"]
        if d in occupied or in_any_range(d, conf_ranges):
            while d in occupied or in_any_range(d, conf_ranges):
                d += timedelta(days=1)
            df_shifted.at[idx, "Date"] = d
        occupied.add(d)

# ───────── Filter for Display ─────────
filtered = df_shifted[df_shifted["Task Type"].isin(display_types)].copy()
if search_topic:
    filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

tasks_by_day = defaultdict(list)
for _, r in filtered.iterrows():
    tasks_by_day[r["Date"]].append((r["Task Type"], r["Topic"]))

# ───────── Clear Completions Helper ─────────
if st.button("🧹 Clear Completions for This Week"):
    for day in week_days:
        for idx, (t, top) in enumerate(tasks_by_day.get(day, [])):
            key = f"cb_{day.isoformat()}_{t}_{top}_{idx}"
            if key in st.session_state:
                st.session_state[key] = False
    st.experimental_rerun()

# ───────── Color Map ─────────
color_map = {
    "Study Date":    "#1f77b4",
    "1-Day Review":  "#ff7f0e",
    "3-Day Review":  "#2ca02c",
    "7-Day Review":  "#d62728",
    "14-Day Review": "#9467bd",
    "30-Day Review": "#8c564b",
    "60-Day Review": "#e377c2",
    "Final Review":  "#7f7f7f",
    "Full Length Exam": "#4361ee",
}

# ───────── Render Weekly View ─────────
total_remaining = 0
for day in week_days:
    for idx, (t, top) in enumerate(tasks_by_day.get(day, [])):
        if not st.session_state.get(f"cb_{day.isoformat()}_{t}_{top}_{idx}", False):
            total_remaining += 1

st.markdown(
    f"<h2 style='margin-bottom:10px;'>Total tasks remaining this week: {total_remaining}</h2>",
    unsafe_allow_html=True,
)
if st.session_state["selected_date"] >= date(2025, 7, 1):
    st.markdown(
        "<div style='background-color:#e63946; color:white; padding:12px; border-radius:6px; font-size:1.1em; margin-bottom:20px;'>"
        "📖 <strong>Daily Reminder:</strong> Complete 40 Practice Questions every day!"
        "</div>",
        unsafe_allow_html=True,
    )
st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)
if total_remaining == 0:
    st.info("🎉 All tasks for this week are completed!")

cols = st.columns(7)
for i, day in enumerate(week_days):
    with cols[i]:
        st.markdown(
            f"<div style='margin-bottom:12px;'><strong>{calendar.day_name[day.weekday()]}</strong><br>{day.strftime('%b %d')}</div>",
            unsafe_allow_html=True,
        )
        d_tasks = tasks_by_day.get(day, [])
        if not d_tasks:
            st.markdown(
                "<div style='color:gray; font-style:italic; margin-bottom:12px;'>No tasks</div>",
                unsafe_allow_html=True,
            )
        else:
            for idx, (t, top) in enumerate(d_tasks):
                key = f"cb_{day.isoformat()}_{t}_{top}_{idx}"
                comp = st.checkbox("", key=key)
                color = color_map.get(t, "#000000")
                if not comp:
                    st.markdown(
                        f"<div style='display:inline-block; background-color:{color}; color:white; padding:4px 8px; border-radius:4px; font-size:0.9em; font-weight:500; margin-left:6px; margin-bottom:4px;'>{t}</div>",
                        unsafe_allow_html=True,
                    )
                    if top:
                        st.markdown(
                            f"<div style='margin-left:12px; font-size:0.9em; color:#e0e0e0; margin-bottom:12px;'>{top}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        f"<div style='display:inline-block; background-color:lightgray; color:#666666; padding:4px 8px; border-radius:4px; font-size:0.9em; font-weight:500; margin-left:6px; margin-bottom:4px; text-decoration: line-through;'>{t}</div>",
                        unsafe_allow_html=True,
                    )
                    if top:
                        st.markdown(
                            f"<div style='margin-left:12px; font-size:0.9em; color:#999999; margin-bottom:12px; text-decoration: line-through;'>{top}</div>",
                            unsafe_allow_html=True,
                        )

# ───────── Optional: Raw Data Table ─────────
with st.expander("📋 View Raw Shifted Data Table"):
    st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values("Date"))
