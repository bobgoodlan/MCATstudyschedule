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
    melted = melted.dropna(subset=["Date"])
    melted["Date"] = pd.to_datetime(melted["Date"])

    # ───────── Shift June 23–25 → +3 Days ─────────
    busy_start = datetime(2025, 6, 23).date()
    busy_end   = datetime(2025, 6, 25).date()
    shift_amount = (busy_end - busy_start).days + 1  # 3 days

    def shift_if_june23_to_25(ts: pd.Timestamp) -> pd.Timestamp:
        """
        If ts.date() is June 23, 24, or 25 2025, add exactly 3 days.
        Otherwise, return ts unchanged.
        """
        if pd.isna(ts):
            return ts
        d = ts.date()
        if busy_start <= d <= busy_end:
            return pd.Timestamp(d + timedelta(days=shift_amount))
        return ts

    melted["Date"] = melted["Date"].apply(shift_if_june23_to_25)
    # ────────────────────────────────────────────────────

    # ───────── Sidebar Controls ─────────
    st.sidebar.header("🔍 Filters")

    # 1) Week selector (choose any date; we'll show Mon–Sun of that week)
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
    filtered = melted[melted["Task Type"].isin(selected_types)]
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
            # Day header, e.g. “Monday Jun 09”
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

                    # Two mini‐columns: [checkbox] [pill+topic combined]
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
