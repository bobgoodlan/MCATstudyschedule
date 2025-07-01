import streamlit as st
import pandas as pd
from datetime import date, timedelta
import random
import io

# ───────── Page Configuration ─────────
st.set_page_config(page_title="📆 Daily Topic Review", layout="wide")
st.title("📚 Daily Topic Review Schedule")

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

# ───────── Generate Schedule ─────────
@st.cache_data
def generate_schedule(topics, start_dt, end_dt, per_day):
    days = (end_dt - start_dt).days + 1
    pool = topics.copy()
    random.shuffle(pool)
    schedule = []
    for offset in range(days):
        # Refill and reshuffle if not enough topics
        if len(pool) < per_day:
            pool = topics.copy()
            random.shuffle(pool)
        today_topics = pool[:per_day]
        pool = pool[per_day:]
        schedule.append({
            "Date": start_dt + timedelta(days=offset),
            **{f"Topic {i+1}": topic for i, topic in enumerate(today_topics)}
        })
    return schedule

schedule = generate_schedule(TOPICS, START_DATE, END_DATE, TOPICS_PER_DAY)

df = pd.DataFrame(schedule)
df.set_index("Date", inplace=True)
\# ───────── Display Schedule ─────────
st.subheader(f"Review Schedule: {START_DATE.strftime('%b %d, %Y')} – {END_DATE.strftime('%b %d, %Y')}")
st.dataframe(df)

# ───────── Download as Excel ─────────
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df.to_excel(writer, sheet_name="Review Schedule")
output.seek(0)

st.download_button(
    label="📥 Download Schedule as Excel",
    data=output,
    file_name="daily_review_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
