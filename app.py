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
        If ts falls on 6/23–6/25/2025 and is a “Study Date”, keep adding one day
        until it lands after 6/25. Otherwise, return ts unchanged.
        """
        if pd.isna(ts):
            return ts
        d = ts.date()
        while busy_start <= d <= busy_end:
            d += timedelta(days=1)
        return pd.Timestamp(d)

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
    st.markdown(
        f"<h2 style='margin-bottom:20px;'>"
        f"Total tasks this week: {total_tasks_this_week}</h2>",
        unsafe_allow_html=True,
    )
    st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

    # Create one column per weekday
    cols = st.columns(7)

    for i, day in enumerate(week_days):
        with cols[i]:
            # Day header with extra bottom margin for spacing
            st.markdown(
                f"<div style='margin-bottom:16px;'>"
                f"<strong>{calendar.day_name[day.weekday()]}</strong><br>"
                f"{day.strftime('%b %d')}</div>",
                unsafe_allow_html=True,
            )

            day_tasks = tasks_by_day.get(day, [])
            if not day_tasks:
                st.markdown("<div style='color:gray; font-style:italic;'>No tasks</div>", unsafe_allow_html=True)
            else:
                for idx, (task_type, topic) in enumerate(day_tasks):
                    # Unique key for each checkbox
                    key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                    color = color_map.get(task_type, "#000000")

                    # Two tiny columns: [checkbox] [card with pill + topic]
                    cb_col, content_col = st.columns([1, 11])
                    with cb_col:
                        st.checkbox("", key=key)
                    with content_col:
                        # A “card” div around pill + topic
                        card_html = (
                            f"<div "
                            f"style='background-color:#2e2e2e; "
                            f"border-radius:8px; padding:10px; margin-bottom:12px; "
                            f"display:flex; align-items:center;'>"
                            # Colored pill
                            f"<span style='background-color:{color}; "
                            f"color:white; padding:4px 8px; border-radius:8px; "
                            f"font-size:0.9em; font-weight:500; margin-right:8px;'>"
                            f"{task_type}</span>"
                            # Topic text
                            f"<span style='font-size:0.9em; color:#e0e0e0;'>"
                            f"{topic}</span>"
                            f"</div>"
                        )
                        st.markdown(card_html, unsafe_allow_html=True)

    # ───────── Optional: Show Data Table ─────────
    with st.expander("📋 View Data Table"):
        st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))

else:
    st.info("Please upload an Excel file to continue.")
