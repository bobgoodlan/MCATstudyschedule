import streamlit as st
import pandas as pd
from datetime import date, timedelta
import random
import io

# ───────── Page Configuration ─────────
st.set_page_config(page_title="📆 Spaced Daily Topic Review", layout="wide")
st.title("📚 Spaced Daily Topic Review Schedule")

# ───────── Fixed Topics List ─────────
TOPICS = [
    "Gen chem 1-2", "Gen chem 3-4", "Gen chem 5-6", "Gen chem 7-8", "Gen chem 9/12", "Gen chem 10/11",
    "Physics 1-2", "Physics 3-4", "Physics 5-6", "Physics 7", "Physics 8-9", "Physics 10-12",
    "O chem 1-2", "O chem 3-4", "O chem 5-6", "O chem 7-8", "O chem 9-10", "O chem 11-12",
    "Behavioural 1-2", "Behavioural 3-4",
    "Biochem 1-2", "Biochem 3-4", "Biochem 5-6", "Biochem 7-8", "Biochem 9", "Biochem 10/11",
    "Bio 1-2", "Bio 3-4", "Bio 5-6", "Bio 7-8", "Bio 9-10", "Bio 11-12",
]

# ───────── Schedule Parameters ─────────
START_DATE = date(2025, 7, 8)
END_DATE = date(2025, 9, 1)
TOPICS_PER_DAY = 4

# ───────── Generate Spaced Schedule ─────────
@st.cache_data
def generate_spaced_schedule(topics, start_dt, end_dt, per_day):
    total_days = (end_dt - start_dt).days + 1
    last_seen = {t: start_dt - timedelta(days=total_days) for t in topics}
    schedule = []

    for day_offset in range(total_days):
        current_date = start_dt + timedelta(days=day_offset)
        # If Thursday → FL practice exam
        if current_date.weekday() == 3:  # Monday=0, Thursday=3
            schedule.append({
                "Date": current_date,
                "Activity": "FL Practice Exam"
            })
            continue

        # Otherwise, pick topics as before
        pool = topics.copy()
        random.shuffle(pool)
        pool.sort(key=lambda t: last_seen[t])
        today_topics = pool[:per_day]
        for t in today_topics:
            last_seen[t] = current_date

        entry = {"Date": current_date}
        for i, topic in enumerate(today_topics, start=1):
            entry[f"Topic {i}"] = topic
        schedule.append(entry)

    return schedule

# ───────── Build Schedule DataFrame ─────────
schedule = generate_spaced_schedule(TOPICS, START_DATE, END_DATE, TOPICS_PER_DAY)
df = pd.DataFrame(schedule).set_index("Date")

# ───────── Compute Average Spacing ─────────
long_df = (
    df
    .reset_index()
    .melt(
        id_vars=["Date"],
        value_vars=[f"Topic {i}" for i in range(1, TOPICS_PER_DAY + 1)],
        var_name="Position",
        value_name="Topic"
    )
    .dropna(subset=["Topic"])  # exclude Thursdays
)

gaps = []
for topic, group in long_df.groupby("Topic"):
    dates = group["Date"].sort_values()
    deltas = dates.diff().dt.days.dropna()
    gaps.extend(deltas.tolist())

avg_gap = sum(gaps) / len(gaps) if gaps else 0

# ───────── Display Schedule and Metrics ─────────
st.subheader(f"Spaced Review: {START_DATE.strftime('%b %d, %Y')} → {END_DATE.strftime('%b %d, %Y')}")
st.markdown(f"**Average spacing between topic reviews:** {avg_gap:.1f} days")
st.dataframe(df)

# ───────── Export to Excel ─────────
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Spaced Review")
buffer.seek(0)

st.download_button(
    label="📥 Export to Excel",
    data=buffer,
    file_name="spaced_daily_review_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
