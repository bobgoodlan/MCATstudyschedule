import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 Study Schedule Weekly Planner")

# Upload Excel File
uploaded_file = st.file_uploader("Upload your MCAT Study Schedule Excel file", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    df_master = xls.parse("Master")

    # Melt the DataFrame to long format
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

    # Drop any rows where Date is missing, then convert to datetime
    melted = melted.dropna(subset=["Date"])
    melted["Date"] = pd.to_datetime(melted["Date"])

    # ─────── “Shift Busy” Logic ───────
    # Define the busy‐date range (inclusive)
    busy_start = datetime(2025, 6, 23).date()
    busy_end = datetime(2025, 6, 25).date()

    def shift_if_busy(ts: pd.Timestamp) -> pd.Timestamp:
        """
        If ts.date() falls between 2025-06-23 and 2025-06-25 inclusive,
        keep adding one day until we're outside that range.
        """
        if pd.isna(ts):
            return ts

        current_date = ts.date()
        while busy_start <= current_date <= busy_end:
            current_date += timedelta(days=1)
        return pd.Timestamp(current_date)

    # Apply the shifting function to every Date
    melted["Date"] = melted["Date"].apply(shift_if_busy)
    # ───────────────────────────────────

    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    task_types = melted["Task Type"].unique().tolist()
    selected_types = st.sidebar.multiselect("Task Types", task_types, default=task_types)
    search_topic = st.sidebar.text_input("Search Topic")

    # Filter data based on user selections
    filtered = melted[melted["Task Type"].isin(selected_types)]
    if search_topic:
        filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

    # Group tasks by date, storing (task_type, topic) tuples
    tasks_by_day = defaultdict(list)
    for _, row in filtered.iterrows():
        tasks_by_day[row["Date"].date()].append((row["Task Type"], row["Topic"]))

    # Determine the current week (Monday–Sunday)
    today = datetime.today().date()
    week_start = today - timedelta(days=today.weekday())  # Monday of this week
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # Calculate total tasks for the week (after filtering/shifting)
    total_tasks_this_week = sum(len(tasks_by_day.get(day, [])) for day in week_days)

    # Define a color map for each Task Type
    color_map = {
        "Study Date": "#1f77b4",      # blue
        "1-Day Review": "#ff7f0e",    # orange
        "3-Day Review": "#2ca02c",    # green
        "7-Day Review": "#d62728",    # red
        "14-Day Review": "#9467bd",   # purple
        "30-Day Review": "#8c564b",   # brown
        "60-Day Review": "#e377c2",   # pink
        "Final Review": "#7f7f7f",    # gray
    }

    # ────────── Display Weekly View ──────────
    st.markdown(f"**Total tasks this week:** {total_tasks_this_week}")

    st.markdown("### 📆 Weekly View")
    cols = st.columns(7)
    for i, day in enumerate(week_days):
        with cols[i]:
            st.markdown(
                f"**{calendar.day_name[day.weekday()]}<br>{day.strftime('%b %d')}**",
                unsafe_allow_html=True,
            )

            day_tasks = tasks_by_day.get(day, [])
            if not day_tasks:
                st.markdown("_No tasks_")
            else:
                # For each task (task_type, topic), render a colored checkbox
                for idx, (task_type, topic) in enumerate(day_tasks):
                    # Unique key per checkbox so Streamlit can manage state
                    key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"

                    # Create two mini‐columns: checkbox + colored label
                    cb_col, label_col = st.columns([1, 11])
                    with cb_col:
                        st.checkbox("", key=key)
                    with label_col:
                        color = color_map.get(task_type, "#000000")
                        st.markdown(
                            f"<span style='color:{color}'>{task_type}: {topic}</span>",
                            unsafe_allow_html=True,
                        )

    # ─── Optional: Display the filtered data as a table ───
    with st.expander("📋 View Data Table"):
        st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))

else:
    st.info("Please upload an Excel file to continue.")
