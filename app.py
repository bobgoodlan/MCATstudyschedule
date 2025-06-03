import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 Study Schedule Weekly Planner")

# ───────── Upload Excel File ─────────
uploaded_file = st.file_uploader("Upload your MCAT Study Schedule Excel file", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    df_master = xls.parse("Master")

    # ─────── Melt to Long Format ───────
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

    # Drop rows without a Date, then convert to datetime
    melted = melted.dropna(subset=["Date"]).copy()
    melted["Date"] = pd.to_datetime(melted["Date"])

    # ───────── Shift “Study Date” Tasks Only ─────────
    busy_start = datetime(2025, 6, 23).date()
    busy_end   = datetime(2025, 6, 25).date()

    def shift_study_date(ts: pd.Timestamp) -> pd.Timestamp:
        if pd.isna(ts):
            return ts
        d = ts.date()
        # Only shift if this is a “Study Date” and falls on 6/23–6/25
        if busy_start <= d <= busy_end:
            while busy_start <= d <= busy_end:
                d += timedelta(days=1)
            return pd.Timestamp(d)
        return ts

    # Apply only to “Study Date” rows
    is_study = melted["Task Type"] == "Study Date"
    melted.loc[is_study, "Date"] = melted.loc[is_study, "Date"].apply(shift_study_date)

    # ── Prevent multiple “Study Date” tasks on the same day ──
    study_df = melted[is_study].copy()
    occupied = set()
    for idx, row in study_df.sort_values("Date").iterrows():
        d = row["Date"].date()
        if d not in occupied:
            occupied.add(d)
        else:
            candidate = d + timedelta(days=1)
            while (busy_start <= candidate <= busy_end) or (candidate in occupied):
                candidate += timedelta(days=1)
            melted.at[idx, "Date"] = pd.Timestamp(candidate)
            occupied.add(candidate)
    # ────────────────────────────────────────────────────────

    # ───────── Sidebar Controls ─────────
    st.sidebar.header("🔍 Filters")

    # 1) Week selector (Mon–Sun of that week)
    selected_date = st.sidebar.date_input(
        "Select a date (to view that week):", value=datetime.today().date()
    )
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # 2) Task‐Type filter
    task_types = melted["Task Type"].unique().tolist()
    selected_types = st.sidebar.multiselect("Task Types", task_types, default=task_types)

    # 3) Topic keyword search
    search_topic = st.sidebar.text_input("Search Topic")

    # ───────── Filter the Data ─────────
    filtered = melted[melted["Task Type"].isin(selected_types)].copy()
    if search_topic:
        filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

    # Group into a dict: { date → list of (task_type, topic) }
    tasks_by_day = defaultdict(list)
    for _, row in filtered.iterrows():
        tasks_by_day[row["Date"].date()].append((row["Task Type"], row["Topic"]))

    # ───────── Compute Weekly Totals ─────────
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

    # ───────── Display the Week ─────────
    st.markdown(f"<h2>Total tasks this week: {total_tasks_this_week}</h2>", unsafe_allow_html=True)
    st.markdown("### 📆 Weekly View")

    # Create 7 columns—one per day
    cols = st.columns(7)

    for i, day in enumerate(week_days):
        with cols[i]:
            # Day header: “Wednesday Jun 11”
            st.markdown(
                f"**{calendar.day_name[day.weekday()]}<br>{day.strftime('%b %d')}**",
                unsafe_allow_html=True,
            )

            day_tasks = tasks_by_day.get(day, [])
            if not day_tasks:
                st.markdown("_No tasks_")
            else:
                # Render each task in a tight, flex‐aligned <div>
                for idx, (task_type, topic) in enumerate(day_tasks):
                    key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                    color = color_map.get(task_type, "#000000")

                    # Two mini‐columns: [checkbox] [content → pill + topic]
                    cb_col, content_col = st.columns([1, 12])
                    with cb_col:
                        st.checkbox("", key=key)
                    with content_col:
                        # Use a single <div> with display:flex and small margin‐bottom
                        # to keep pill + topic on one line, with minimal spacing.
                        html = (
                            f"<div style='display:flex; align-items:center; "
                            f"margin-bottom:4px;'>"
                            # Colored pill, smaller font
                            f"<span style='background-color:{color}; "
                            f"color:white; padding:2px 6px; border-radius:4px; "
                            f"font-size:0.85em; display:inline-block;'>"
                            f"{task_type}</span>"
                            # Small gap before topic text
                            f"<span style='margin-left:6px; font-size:0.9em;'>"
                            f"{topic}</span>"
                            f"</div>"
                        )
                        st.markdown(html, unsafe_allow_html=True)

    # ───────── Optional: Data Table ─────────
    with st.expander("📋 View Data Table"):
        st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))

else:
    st.info("Please upload an Excel file to continue.")
