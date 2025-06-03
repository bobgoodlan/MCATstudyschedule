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
    df_master = xls.parse('Master')

    # Melt the DataFrame to long format
    melted = pd.melt(
        df_master,
        id_vars=['Topic'],
        value_vars=[
            'Study Date',
            '1-Day Review',
            '3-Day Review',
            '7-Day Review',
            '14-Day Review',
            '30-Day Review',
            '60-Day Review',
            'Final Review'
        ],
        var_name='Task Type',
        value_name='Date'
    )

    # Drop any rows where Date is missing, then convert to datetime
    melted = melted.dropna(subset=['Date'])
    melted['Date'] = pd.to_datetime(melted['Date'])

    # ─────── “Shift Busy” Logic ───────
    # Define the busy‐date range (inclusive)
    busy_start = datetime(2025, 6, 23).date()
    busy_end   = datetime(2025, 6, 25).date()

    def shift_if_busy(ts: pd.Timestamp) -> pd.Timestamp:
        """
        If ts.date() falls between 2025-06-23 and 2025-06-25 inclusive,
        keep adding one day until we're outside that range.
        """
        if pd.isna(ts):
            return ts

        current_date = ts.date()
        # While it's in the busy window, bump forward
        while busy_start <= current_date <= busy_end:
            current_date += timedelta(days=1)
        return pd.Timestamp(current_date)

    # Apply the shifting function to every Date
    melted['Date'] = melted['Date'].apply(shift_if_busy)
    # ───────────────────────────────────

    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    task_types     = melted['Task Type'].unique().tolist()
    selected_types = st.sidebar.multiselect("Task Types", task_types, default=task_types)
    search_topic   = st.sidebar.text_input("Search Topic")

    # Filter data based on user selections
    filtered = melted[melted['Task Type'].isin(selected_types)]
    if search_topic:
        filtered = filtered[filtered['Topic'].str.contains(search_topic, case=False, na=False)]

    # Group tasks by date
    tasks_by_day = defaultdict(list)
    for _, row in filtered.iterrows():
        tasks_by_day[row['Date'].date()].append(f"{row['Task Type']}: {row['Topic']}")

    # Determine the current week (Monday–Sunday)
    today      = datetime.today().date()
    week_start = today - timedelta(days=today.weekday())  # Monday of this week
    week_days  = [week_start + timedelta(days=i) for i in range(7)]

    # Display calendar‐style layout
    st.markdown("### 📆 Weekly View")
    cols = st.columns(7)
    for i, day in enumerate(week_days):
        with cols[i]:
            st.markdown(
                f"**{calendar.day_name[day.weekday()]}<br>{day.strftime('%b %d')}**",
                unsafe_allow_html=True
            )
            day_tasks = tasks_by_day.get(day, [])
            if not day_tasks:
                st.markdown("_No tasks_")
            for task in day_tasks:
                st.markdown(f"- {task}")

    # Optional: Display the filtered data as a table
    with st.expander("📋 View Data Table"):
        st.dataframe(filtered[['Date', 'Task Type', 'Topic']].sort_values(by='Date'))

else:
    st.info("Please upload an Excel file to continue.")
