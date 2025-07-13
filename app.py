import streamlit as st
import pandas as pd
from datetime import date, timedelta
import random
import io

# ───────── Page Configuration ─────────
st.set_page_config(page_title="📆 Spaced Daily Topic Review (Optimized)", layout="wide")
st.title("📚 Spaced Daily Topic Review Schedule (min-avg-spacing)")

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
END_DATE   = date(2025, 9, 1)
TOPICS_PER_DAY = 4
VACATION_DAYS = {date(2025, 7, 11), date(2025, 7, 12), date(2025, 7, 13)}

# ───────── Generate One Candidate Schedule ─────────
def generate_schedule(topics, start_dt, end_dt, per_day, seed):
    random.seed(seed)
    total_days = (end_dt - start_dt).days + 1
    last_seen = {t: start_dt - timedelta(days=total_days) for t in topics}
    sched = []

    for i in range(total_days):
        today = start_dt + timedelta(days=i)

        if today in VACATION_DAYS:
            sched.append({"Date": today, "Activity": "Vacation"})
            continue

        if today.weekday() == 3:  # Thursday → FL Practice Exam
            sched.append({"Date": today, "Activity": "FL Practice Exam"})
            continue

        pool = topics.copy()
        random.shuffle(pool)
        pool.sort(key=lambda t: last_seen[t])

        today_topics, seen_subj = [], set()
        for topic in pool:
            subj = " ".join(topic.split()[:-1])
            if subj in seen_subj:
                continue
            today_topics.append(topic)
            seen_subj.add(subj)
            last_seen[topic] = today
            if len(today_topics) == per_day:
                break

        entry = {"Date": today}
        for idx, t in enumerate(today_topics, 1):
            entry[f"Topic {idx}"] = t
        sched.append(entry)

    return sched

# ───────── Compute Average Gap ─────────
def avg_spacing(schedule):
    df_long = (
        pd.DataFrame(schedule)
          .melt(id_vars=["Date"], value_vars=[f"Topic {i}" for i in range(1, TOPICS_PER_DAY+1)],
                var_name="Pos", value_name="Topic")
          .dropna(subset=["Topic"])
    )
    gaps = []
    for _, grp in df_long.groupby("Topic"):
        dts = grp["Date"].sort_values()
        gaps.extend(dts.diff().dt.days.dropna().tolist())
    return (sum(gaps)/len(gaps)) if gaps else float("inf")

# ───────── Trial Loop ─────────
trials = st.sidebar.number_input("Optimization trials", min_value=10, max_value=2000, value=200, step=10)
best = {"avg": float("inf"), "sched": None}

for seed in range(trials):
    cand = generate_schedule(TOPICS, START_DATE, END_DATE, TOPICS_PER_DAY, seed)
    a = avg_spacing(cand)
    if a < best["avg"]:
        best.update(avg=a, sched=cand)

# ───────── Build DataFrame & Show ─────────
df = pd.DataFrame(best["sched"]).set_index("Date")
st.subheader(f"Best average spacing: {best['avg']:.1f} days (over {trials} trials)")
st.dataframe(df)

# ───────── Export to Excel ─────────
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Spaced Review")
buf.seek(0)

st.download_button(
    label="📥 Export Optimized Schedule",
    data=buf,
    file_name="optimized_spaced_review.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
