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
    # We only want to push Study Date tasks off of 6/23, 6/24, 6/25.
    busy_start = datetime(2025, 6, 23).date()
    busy_end   = datetime(2025, 6, 25).date()

    def shift_study_date(ts: pd.Timestamp) -> pd.Timestamp:
        """
        Assumes ts is a Timestamp for a “Study Date” row.
        If ts.date() is 6/23, 6/24, or 6/25/2025, keep adding +1 day
        until the date is > 6/25. Otherwise return ts unchanged.
        """
        if pd.isna(ts):
            return ts
        current_date = ts.date()
        while busy_start <= current_date <= busy_end:
            current_date += timedelta(days=1)
        return pd.Timestamp(current_date)

    # Build a mask for “Study Date” rows in our melted DataFrame
    is_study = melted["Task Type"] == "Study Date"

    # Only apply the shifting function to those “Study Date” rows
    melted.loc[is_study, "Date"] = melted.loc[is_study, "Date"].apply(shift_study_date)
    # All other rows (reviews) keep their original Date, even if it’s 6/23–6/25
    # ─────────────────────────────────────────────────────────

    # ── Prevent multiple “Study Date” tasks on the same day ──
    # (We’ve already shifted each “Study Date” so none land on 6/23–6/25.
    # But we still want no two “Study Date” tasks on exactly the same date.)
    study_df = melted[is_study].copy()
    occupied = set()  # track which dates already have a Study Date

    # Sort by Date so we fill earlier days first, then move conflicted ones forward
    for idx, row in study_df.sort_values("Date").iterrows():
        d = row["Date"].date()
        if d not in occupied:
            occupied.add(d)
        else:
            # If this exact date is already taken, bump forward until we find a free day
            candidate = d + timedelta(days=1)
            # Skip over any date in [6/23, 6/25] (conference) or anything in occupied
            while (busy_start <= candidate <= busy_end) or (candidate in occupied):
                candidate += timedelta(days=1)
            melted.at[idx, "Date"] = pd.Timestamp(candidate)
            occupied.add(candidate)
    # ────────────────────────────────────────────────────────

    # ───────── Sidebar Controls ─────────
    st.sidebar.header("🔍 Filters")

    # 1) Week selector (choose any date; we'll show Mon–Sun of that week)
    selected_date = st.sidebar.date_input(
        "Select a date (to view that week):", value=datetime.today().date()
    )
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # 2) Task-Type filter
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
    # 1) Show a bigger “Total tasks this week”
    st.markdown(f"<h2>Total tasks this week: {total_tasks_this_week}</h2>", unsafe_allow_html=True)

    # 2) Show Monday–Sunday columns
    st.markdown("### 📆 Weekly View")
    cols = st.columns(7)

    for i, day in enumerate(week_days):
        with cols[i]:
            # Day header, e.g. “Thursday Jun 19”
            st.markdown(
                f"**{calendar.day_name[day.weekday()]}<br>{day.strftime('%b %d')}**",
                unsafe_allow_html=True,
            )

            day_tasks = tasks_by_day.get(day, [])
            if not day_tasks:
                st.markdown("_No tasks_")
            else:
                for idx, (task_type, topic) in enumerate(day_tasks):
                    # Unique key for each checkbox (date, type, topic, index)
                    key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"

                    # Two mini-columns: [checkbox] [pill+topic combined]
                    cb_col, content_col = st.columns([1, 11])
                    with cb_col:
                        st.checkbox("", key=key)
                    with content_col:
                        # Render pill + topic on one horizontal line
                        color = color_map.get(task_type, "#000000")
                        st.markdown(
                            f"<span style='background-color:{color};"
                            f" color:white; padding:2px 6px; border-radius:4px; "
                            f"font-size:0.9em; display:inline-block;'>"
                            f"{task_type}</span>"
                            f"&nbsp;<span style='vertical-align:middle;'>{topic}</span>",
                            unsafe_allow_html=True,
                        )

    # ───────── Optional: Show Data Table ─────────
    with st.expander("📋 View Data Table"):
        st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))

else:
    st.info("Please upload an Excel file to continue.")
