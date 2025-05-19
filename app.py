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

def badge(task_type):
    color = COLOR_MAP.get(task_type, '#000000')
    return f"<span style='background-color:{color};color:white;border-radius:3px;padding:2px 6px;font-size:0.8em'>{task_type}</span>"

# ─── File Upload ───────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload your MCAT Study Schedule Excel file", type=["xlsx"])
if not uploaded_file:
    st.info("Please upload an Excel file to continue.")
    st.stop()

melted = load_schedule(uploaded_file)

# ─── Sidebar: Filters + Week Controls ──────────────────────────────────────────
st.sidebar.header("🔍 Filters & Navigation")
task_types = melted['Task Type'].unique().tolist()
selected_types = st.sidebar.multiselect("Task Types", task_types, default=task_types)
search_topic = st.sidebar.text_input("Search Topic")

today = datetime.today().date()
if 'week_start' not in st.session_state:
    st.session_state.week_start = today - timedelta(days=today.weekday())

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

tasks_by_day = defaultdict(list)
for _, row in filtered.iterrows():
    # build a unique key for each task
    key = f"{row['Date']}_{row['Task Type']}_{row['Topic']}"
    tasks_by_day[row['Date']].append((row['Task Type'], row['Topic'], key))

# ─── Summary Metrics ───────────────────────────────────────────────────────────
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

# ─── Weekly Calendar View with Checkboxes ─────────────────────────────────────
# ─── Weekly Calendar View with Checkboxes ─────────────────────────────────────
st.markdown("### 📆 Weekly View")
cols = st.columns(7)
for idx, day in enumerate(week_days):
    with cols[idx]:
        st.markdown(f"**{calendar.day_name[day.weekday()]}**  \n{day.strftime('%b %d')}")
        day_list = tasks_by_day.get(day, [])
        if not day_list:
            st.markdown("_No tasks_")
            continue

        for tp, topic, key in day_list:
            # Create two mini-columns: one for the checkbox, one for the HTML badge & text
            cb_col, txt_col = st.columns([1, 9])
            done = cb_col.checkbox(
                label="", 
                key=key, 
                value=st.session_state.get(key, False)
            )
            st.session_state[key] = done

            # Render badge + topic, with strikethrough if done
            display_text = (
                f"{badge(tp)} <span style='text-decoration:line-through;color:gray'>{topic}</span>"
                if done
                else f"{badge(tp)} {topic}"
            )
            txt_col.markdown(display_text, unsafe_allow_html=True)

# ─── Optional: Raw Data ────────────────────────────────────────────────────────
with st.expander("📋 View Raw Data Table"):
    st.dataframe(filtered[['Date','Task Type','Topic']].sort_values(['Date','Task Type']), height=300)
