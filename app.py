import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Study Schedule Calendar", layout="wide")
st.title("📚 MCAT Study Schedule Weekly Planner")

# ─── Helpers ────────────────────────────────────────────────────────────────────
@st.cache_data
def load_schedule(file):
    xls = pd.ExcelFile(file)
    df = xls.parse('Master')
    melted = pd.melt(
        df,
        id_vars=['Topic'],
        value_vars=[
            'Study Date', '1-Day Review', '3-Day Review', '7-Day Review',
            '14-Day Review', '30-Day Review', '60-Day Review', 'Final Review'
        ],
        var_name='Task Type',
        value_name='Date'
    ).dropna(subset=['Date'])
    melted['Date'] = pd.to_datetime(melted['Date']).dt.date
    return melted

# Color map for badges
COLOR_MAP = {
    'Study Date': '#1f77b4',
    '1-Day Review': '#ff7f0e',
    '3-Day Review': '#2ca02c',
    '7-Day Review': '#d62728',
    '14-Day Review': '#9467bd',
    '30-Day Review': '#8c564b',
    '60-Day Review': '#e377c2',
    'Final Review': '#7f7f7f',
}

def badge(task_type, text):
    color = COLOR_MAP.get(task_type, '#000000')
    return f"<span style='background-color:{color};color:white;border-radius:3px;padding:2px 6px;font-size:0.9em'>{text}</span>"

# ─── File Upload ───────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload your MCAT Study Schedule Excel file", type=["xlsx"])
if not uploaded_file:
    st.info("Please upload an Excel file to continue.")
    st.stop()

melted = load_schedule(uploaded_file)

# ─── Sidebar: Filters + Week Controls ──────────────────────────────────────────
st.sidebar.header("🔍 Filters & Navigation")

# Task-type & topic filter
task_types = melted['Task Type'].unique().tolist()
selected_types = st.sidebar.multiselect("Task Types", task_types, default=task_types)
search_topic = st.sidebar.text_input("Search Topic")

# Week navigation
today = datetime.today().date()
# Initialize session state for week_start
if 'week_start' not in st.session_state:
    st.session_state.week_start = today - timedelta(days=today.weekday())

# Jump to a date
pick = st.sidebar.date_input("Jump to week containing…", value=today)
if pick != today:
    st.session_state.week_start = pick - timedelta(days=pick.weekday())

col1, col2 = st.sidebar.columns(2)
if col1.button("◀ Previous Week"):
    st.session_state.week_start -= timedelta(days=7)
if col2.button("Next Week ▶"):
    st.session_state.week_start += timedelta(days=7)

week_start = st.session_state.week_start
week_days = [week_start + timedelta(days=i) for i in range(7)]

# ─── Data Filtering ────────────────────────────────────────────────────────────
filtered = melted[melted['Task Type'].isin(selected_types)]
if search_topic:
    filtered = filtered[filtered['Topic'].str.contains(search_topic, case=False, na=False)]

# Build tasks_by_day
tasks_by_day = defaultdict(list)
for _, row in filtered.iterrows():
    tasks_by_day[row['Date']].append((row['Task Type'], row['Topic']))

# ─── Summary Metrics ───────────────────────────────────────────────────────────
# Count tasks in current week
week_tasks = [
    t for date in week_days
       for t in tasks_by_day.get(date, [])
]
counts_by_day = {date: len(tasks_by_day.get(date, [])) for date in week_days}

st.markdown("### 📊 This Week’s Summary")
c1, c2 = st.columns([1,3])
with c1:
    st.metric("Total Tasks", len(week_tasks))
with c2:
    st.bar_chart(pd.Series(counts_by_day), use_container_width=True)

# ─── Weekly Calendar View ──────────────────────────────────────────────────────
st.markdown("### 📆 Weekly View")
cols = st.columns(7)
for idx, day in enumerate(week_days):
    with cols[idx]:
        st.markdown(f"**{calendar.day_name[day.weekday()]}**  \n{day.strftime('%b %d')}")
        day_list = tasks_by_day.get(day, [])
        if not day_list:
            st.markdown("_No tasks_")
        for tp, topic in day_list:
            st.markdown(badge(tp, tp.split()[0]) + f"  {topic}", unsafe_allow_html=True)

# ─── Optional: Raw Data ────────────────────────────────────────────────────────
with st.expander("📋 View Raw Data Table"):
    st.dataframe(filtered[['Date','Task Type','Topic']].sort_values(['Date','Task Type']), height=300)
