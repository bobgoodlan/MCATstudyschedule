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

    # ───────── Define Busy Windows ─────────
    # 1) Missed‐Review window: May 31 – June 1, 2025
    missed_start = datetime(2025, 5, 31).date()
    missed_end   = datetime(2025, 6, 2).date()
    #   We'll push any Review-type tasks in that window forward by 2 days:
    #   May 31 → June 2, June 1 → June 3
    
    # 2) Conference window for “Study Date”: June 23–25, 2025
    conf_start = datetime(2025, 6, 23).date()
    conf_end   = datetime(2025, 6, 25).date()

    def shift_review_if_missed(ts: pd.Timestamp, task_type: str) -> pd.Timestamp:
        """
        If this is a “Review” task and its date falls on May 31 or June 1 2025,
        push it forward by 2 days so it lands on June 2 or June 3. Otherwise unchanged.
        """
        if pd.isna(ts):
            return ts
        d = ts.date()
        # Only shift for “Review” tasks in the missed window
        if ("Review" in task_type) and (missed_start <= d <= missed_end):
            # Shift by (missed_end - missed_start + 1) = 2 days
            return pd.Timestamp(d + timedelta(days=(missed_end - missed_start).days + 1))
        return ts

    def shift_study_if_conf(ts: pd.Timestamp, task_type: str) -> pd.Timestamp:
        """
        If this is a “Study Date” and its date falls on June 23–25 2025,
        keep pushing forward until it lands after June 25. Otherwise unchanged.
        """
        if pd.isna(ts):
            return ts
        d = ts.date()
        # Only shift for “Study Date” tasks in the conference window
        if (task_type == "Study Date") and (conf_start <= d <= conf_end):
            while conf_start <= d <= conf_end:
                d += timedelta(days=1)
            return pd.Timestamp(d)
        return ts

    # ───────── Apply Shifts ─────────
    # 1) First push reviews out of May 31–June 1
    melted["Date"] = melted.apply(
        lambda row: shift_review_if_missed(row["Date"], row["Task Type"]), axis=1
    )
    # 2) Then push “Study Date” out of June 23–25
    melted["Date"] = melted.apply(
        lambda row: shift_study_if_conf(row["Date"], row["Task Type"]), axis=1
    )

    # ── Prevent multiple “Study Date” tasks on the same day ──
    # (If two “Study Date” tasks land on the same date after shifting, bump
    #  the later‐one forward until it finds a free day outside the conf window.)
    is_study = melted["Task Type"] == "Study Date"
    study_df = melted[is_study].copy()
    occupied = set()
    for idx, row in study_df.sort_values("Date").iterrows():
        d = row["Date"].date()
        if d not in occupied:
            occupied.add(d)
        else:
            candidate = d + timedelta(days=1)
            # Skip over the conference window or any date already taken
            while (conf_start <= candidate <= conf_end) or (candidate in occupied):
                candidate += timedelta(days=1)
            melted.at[idx, "Date"] = pd.Timestamp(candidate)
            occupied.add(candidate)
    # ────────────────────────────────────────────────────────

    # ───────── Sidebar Controls ─────────
    st.sidebar.header("🔍 Filters")

    # 1) Week picker: choose any date, then show Mon–Sun of that week
    selected_date = st.sidebar.date_input(
        "Select a date (to view that week):", value=datetime.today().date()
    )
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # 2) Task‐Type filter (multi‐select)
    task_types = melted["Task Type"].unique().tolist()
    selected_types = st.sidebar.multiselect("Task Types", task_types, default=task_types)

    # 3) Topic search
    search_topic = st.sidebar.text_input("Search Topic")

    # ───────── Filter the Data ─────────
    filtered = melted[melted["Task Type"].isin(selected_types)].copy()
    if search_topic:
        filtered = filtered[filtered["Topic"].str.contains(search_topic, case=False, na=False)]

    # Group tasks by date for rendering
    tasks_by_day = defaultdict(list)
    for _, row in filtered.iterrows():
        tasks_by_day[row["Date"].date()].append((row["Task Type"], row["Topic"]))

    # ───────── Compute Weekly Totals ─────────
    total_tasks_this_week = sum(len(tasks_by_day.get(day, [])) for day in week_days)

    # ───────── Color Map (Task Type → Hex Color) ─────────
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

    # ───────── Render the Weekly View ─────────
    st.markdown(
        f"<h2 style='margin-bottom:20px;'>"
        f"Total tasks this week: {total_tasks_this_week}</h2>",
        unsafe_allow_html=True,
    )
    st.markdown("<h3>📆 Weekly View</h3>", unsafe_allow_html=True)

    cols = st.columns(7)
    for i, day in enumerate(week_days):
        with cols[i]:
            # Day header with extra spacing
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
                for idx, (task_type, topic) in enumerate(day_tasks):
                    key = f"cb_{day.isoformat()}_{task_type}_{topic}_{idx}"
                    color = color_map.get(task_type, "#000000")

                    # Two tiny columns: [checkbox] [pill + topic]
                    cb_col, content_col = st.columns([1, 11])
                    with cb_col:
                        st.checkbox("", key=key)
                    with content_col:
                        # Render each task block in its own <div>:
                        task_html = (
                            f"<div style='margin-bottom:12px;'>"
                            # Colored pill on one line
                            f"<div style='display:inline-block; "
                            f"background-color:{color}; color:white; "
                            f"padding:4px 8px; border-radius:4px; "
                            f"font-size:0.9em; font-weight:500; "
                            f"margin-bottom:4px;'>"
                            f"{task_type}</div><br>"
                            # Topic on next line
                            f"<div style='margin-left:6px; "
                            f"font-size:0.9em; color:#e0e0e0;'>"
                            f"{topic}</div>"
                            f"</div>"
                        )
                        st.markdown(task_html, unsafe_allow_html=True)

    # ───────── Optional: Show Data Table ─────────
    with st.expander("📋 View Data Table"):
        st.dataframe(filtered[["Date", "Task Type", "Topic"]].sort_values(by="Date"))

else:
    st.info("Please upload an Excel file to continue.")
