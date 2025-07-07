import streamlit as st
import pandas as pd
from datetime import date, timedelta
import random
import io
from concurrent.futures import ProcessPoolExecutor

# ───────── Page Configuration ─────────
st.set_page_config(page_title="📆 Spaced Review (Optimized)", layout="wide")
st.title("📚 Spaced Review Schedule (min-avg-spacing)")

# ───────── Fixed Topics & Parameters ─────────
TOPICS = [ ... ]  # same as before
START_DATE = date(2025, 7, 8)
END_DATE   = date(2025, 9, 1)
TOPICS_PER_DAY = 4

# ───────── Schedule Generator ─────────
def generate_schedule(seed):
    random.seed(seed)
    total_days = (END_DATE - START_DATE).days + 1
    last_seen = {t: START_DATE - timedelta(days=total_days) for t in TOPICS}
    sched = []

    for i in range(total_days):
        today = START_DATE + timedelta(days=i)
        if today.weekday() == 3:  # Thursday → FL Practice Exam
            sched.append({"Date": today, "Activity": "FL Practice Exam"})
            continue

        pool = TOPICS.copy()
        random.shuffle(pool)
        pool.sort(key=lambda t: last_seen[t])

        today_topics, seen_subj = [], set()
        for t in pool:
            subj = " ".join(t.split()[:-1])
            if subj in seen_subj:
                continue
            today_topics.append(t)
            seen_subj.add(subj)
            last_seen[t] = today
            if len(today_topics) == TOPICS_PER_DAY:
                break

        entry = {"Date": today}
        for idx, t in enumerate(today_topics, 1):
            entry[f"Topic {idx}"] = t
        sched.append(entry)

    return sched

# ───────── Pure-Python Average-Spacing Calculator ─────────
def avg_spacing(sched):
    reviews = {}
    for entry in sched:
        if "Activity" in entry:
            continue
        d = entry["Date"]
        for i in range(1, TOPICS_PER_DAY + 1):
            t = entry.get(f"Topic {i}")
            if t:
                reviews.setdefault(t, []).append(d)

    total, count = 0, 0
    for dates in reviews.values():
        dates.sort()
        for j in range(1, len(dates)):
            total += (dates[j] - dates[j-1]).days
            count += 1
    return (total / count) if count else float("inf")

# ───────── Parallel Trial Loop ─────────
trials = st.sidebar.number_input("Optimization trials", 10, 2000, 500, 10)

best_avg = float("inf")
best_sched = None

with ProcessPoolExecutor() as executor:
    # executor.map will distribute seeds across cores
    for a, sched in executor.map(lambda s: (avg_spacing(generate_schedule(s)),
                                            generate_schedule(s)),
                                 range(trials)):
        if a < best_avg:
            best_avg, best_sched = a, sched

# ───────── Build & Display ─────────
df = pd.DataFrame(best_sched).set_index("Date")
st.subheader(f"Best avg spacing: {best_avg:.1f} days (over {trials} trials)")
st.dataframe(df)

# ───────── Export to Excel ─────────
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Spaced Review")
buf.seek(0)
st.download_button("📥 Export Optimized Schedule", buf,
                   "optimized_spaced_review.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
