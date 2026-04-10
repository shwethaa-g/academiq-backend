"""
AcademIQ Seed Script
Generates:
  - 3 mentors
  - 50 students (split across mentors)
  - 12 weeks of attendance, grade, engagement, sentiment records
  - Pre-seeded RED (8 students) and AMBER (14 students) trajectories
  - Alerts and intervention logs for at-risk students
  - Cohort weekly snapshots

Run from project root:
  python scripts/seed.py
"""

import os
import sys
import uuid
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

db = create_client(SUPABASE_URL, SUPABASE_KEY)
random.seed(42)
NOW = datetime.now(timezone.utc)
CURRENT_WEEK = NOW.isocalendar()[1]
START_WEEK = CURRENT_WEEK - 11  # 12 weeks of history


# ── Helpers ──────────────────────────────────────────────────────────────────

def uid():
    return str(uuid.uuid4())


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def weeks():
    return list(range(START_WEEK, CURRENT_WEEK + 1))


# ── Mentor data ───────────────────────────────────────────────────────────────

MENTORS = [
    {"id": uid(), "name": "Dr. Sarah Chen",    "email": "s.chen@academiq.demo"},
    {"id": uid(), "name": "Prof. James Okafor","email": "j.okafor@academiq.demo"},
    {"id": uid(), "name": "Dr. Priya Sharma",  "email": "p.sharma@academiq.demo"},
]

# ── Student name pool ─────────────────────────────────────────────────────────

FIRST = ["Alex","Jordan","Morgan","Taylor","Casey","Riley","Avery","Quinn","Skylar","Dakota",
         "Reese","Hayden","Peyton","Logan","Blake","Cameron","Finley","Rowan","Sage","Emery",
         "Jamie","Kendall","Drew","Parker","Elliot","Remy","Nico","Sasha","Bobbie","Frankie",
         "Harley","Jesse","Kai","Luca","Mika","Noel","Onyx","Pax","Reed","Shay",
         "Tatum","Uma","Val","Wren","Xen","Yael","Zion","Ari","Beau","Cleo"]

LAST  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Wilson","Moore",
         "Taylor","Anderson","Thomas","Jackson","White","Harris","Martin","Thompson","Young","Lee",
         "Walker","Hall","Allen","King","Wright","Scott","Green","Baker","Adams","Nelson",
         "Carter","Mitchell","Perez","Roberts","Turner","Phillips","Campbell","Parker","Evans","Edwards",
         "Collins","Stewart","Morris","Sanchez","Rogers","Reed","Cook","Morgan","Bell","Murphy"]

PROGRAMMES = [
    "BSc Computer Science",
    "BSc Data Science",
    "BSc Software Engineering",
    "BSc Artificial Intelligence",
    "BSc Cybersecurity",
]


def make_students():
    students = []
    names_used = set()
    mentor_cycle = MENTORS * 20  # enough for 50

    for i in range(50):
        while True:
            name = f"{random.choice(FIRST)} {random.choice(LAST)}"
            if name not in names_used:
                names_used.add(name)
                break
        email = name.lower().replace(" ", ".") + f"{i}@student.academiq.demo"
        students.append({
            "id": uid(),
            "name": name,
            "email": email,
            "programme": random.choice(PROGRAMMES),
            "year": random.randint(1, 4),
            "mentor_id": mentor_cycle[i]["id"],
        })
    return students


# ── Signal generators ─────────────────────────────────────────────────────────

def gen_green_signals(week_idx: int):
    """Healthy student — high attendance, good grades, active."""
    return {
        "attendance_pct": clamp(random.gauss(88, 5), 75, 100),
        "grade": clamp(random.gauss(72, 8), 55, 95),
        "lms_logins": random.randint(5, 12),
        "assignment_submissions": random.randint(3, 5),
        "forum_posts": random.randint(1, 6),
        "sentiment": clamp(random.gauss(0.4, 0.2), 0.0, 1.0),
    }


def gen_amber_signals(week_idx: int):
    """Declining student — steady deterioration over 12 weeks."""
    decay = week_idx / 11  # 0 at start, 1 at end
    return {
        "attendance_pct": clamp(random.gauss(75 - decay * 20, 5), 45, 90),
        "grade": clamp(random.gauss(65 - decay * 15, 8), 40, 80),
        "lms_logins": max(0, int(random.gauss(5 - decay * 3, 1))),
        "assignment_submissions": max(0, int(random.gauss(3 - decay * 1.5, 0.5))),
        "forum_posts": max(0, int(random.gauss(2 - decay, 0.5))),
        "sentiment": clamp(random.gauss(-0.1 - decay * 0.3, 0.15), -0.8, 0.4),
    }


def gen_red_signals(week_idx: int):
    """Crisis student — sharp drop, severe disengagement by week 6+."""
    severity = min(1.0, week_idx / 6)
    return {
        "attendance_pct": clamp(random.gauss(55 - severity * 35, 8), 0, 75),
        "grade": clamp(random.gauss(50 - severity * 25, 10), 10, 65),
        "lms_logins": max(0, int(random.gauss(3 - severity * 3, 1))),
        "assignment_submissions": max(0, int(random.gauss(2 - severity * 2, 0.5))),
        "forum_posts": max(0, int(random.gauss(1 - severity, 0.3))),
        "sentiment": clamp(random.gauss(-0.4 - severity * 0.5, 0.15), -1.0, 0.0),
    }


# ── Risk scoring (inline, no DB dependency) ───────────────────────────────────

def score_student(signals: dict, missed_surveys: int) -> tuple[float, str]:
    att   = (100 - signals["attendance_pct"]) * 0.25
    grade = (100 - signals["grade"]) * 0.25
    lms   = max(0, (1 - signals["lms_logins"] / 7)) * 100 * 0.20
    asn   = (100 - min(100, (signals["assignment_submissions"] / 5) * 100)) * 0.15
    sent  = ((1 - signals["sentiment"]) / 2) * 100 * 0.10
    surv  = min(100, missed_surveys * 33.33) * 0.05
    total = round(min(100, att + grade + lms + asn + sent + surv), 2)
    tier  = "RED" if total >= 70 else ("AMBER" if total >= 45 else "GREEN")
    return total, tier


# ── Main seed ─────────────────────────────────────────────────────────────────

def seed():
    print("🌱 Starting AcademIQ seed...")

    # 1. Mentors
    print("  → Inserting mentors...")
    db.table("mentors").upsert(MENTORS, on_conflict="email").execute()

    # 2. Students
    print("  → Generating 50 students...")
    students = make_students()

    # Assign trajectories
    red_ids   = {s["id"] for s in students[:8]}
    amber_ids = {s["id"] for s in students[8:22]}
    # rest are GREEN

    # 3. Build all weekly records
    print("  → Building 12 weeks of signals...")
    att_rows, grade_rows, eng_rows, sent_rows = [], [], [], []
    final_signals: dict[str, dict] = {}

    for s in students:
        sid = s["id"]
        is_red   = sid in red_ids
        is_amber = sid in amber_ids
        missed = 0

        for i, week in enumerate(weeks()):
            if is_red:
                sig = gen_red_signals(i)
                # RED students miss some surveys
                missed = i // 3
            elif is_amber:
                sig = gen_amber_signals(i)
                missed = i // 5
            else:
                sig = gen_green_signals(i)

            att_rows.append({
                "id": uid(), "student_id": sid, "week": week,
                "attendance_pct": round(sig["attendance_pct"], 2),
            })
            grade_rows.append({
                "id": uid(), "student_id": sid, "week": week,
                "grade": round(sig["grade"], 2),
            })
            eng_rows.append({
                "id": uid(), "student_id": sid, "week": week,
                "lms_logins": sig["lms_logins"],
                "assignment_submissions": sig["assignment_submissions"],
                "forum_posts": sig["forum_posts"],
            })
            sent_rows.append({
                "id": uid(), "student_id": sid, "week": week,
                "sentiment_score": round(sig["sentiment"], 3),
            })

        # Store latest signals for final score
        final_signals[sid] = {"sig": sig, "missed": missed}

    # 4. Insert weekly records in batches
    def batch_insert(table, rows, batch=100):
        for i in range(0, len(rows), batch):
            db.table(table).insert(rows[i:i+batch]).execute()

    # 5. Compute final scores and insert students
    print("  → Computing risk scores and inserting students...")
    student_rows = []
    for s in students:
        sig    = final_signals[s["id"]]["sig"]
        missed = final_signals[s["id"]]["missed"]
        score, tier = score_student(sig, missed)
        student_rows.append({
            **s,
            "risk_score":   score,
            "risk_tier":    tier,
            "last_updated": NOW.isoformat(),
        })

    batch_insert("students", student_rows)
    
    print("  → Inserting attendance records...")
    batch_insert("attendance_records", att_rows)

    print("  → Inserting grade records...")
    batch_insert("grade_records", grade_rows)

    print("  → Inserting engagement records...")
    batch_insert("engagement_records", eng_rows)

    print("  → Inserting sentiment records...")
    batch_insert("sentiment_records", sent_rows)

    

    # 6. Alerts for RED and AMBER students
    print("  → Creating alerts...")
    alert_rows = []
    for s in students:
        sid   = s["id"]
        score = next(r["risk_score"] for r in student_rows if r["id"] == sid)
        tier  = next(r["risk_tier"]  for r in student_rows if r["id"] == sid)
        if tier in ("RED", "AMBER"):
            alert_rows.append({
                "id": uid(),
                "student_id": sid,
                "severity": tier,
                "trigger": (
                    "Attendance below 60% and multiple assignments missed"
                    if tier == "RED"
                    else "Declining attendance and grade average"
                ),
                "actioned": tier == "AMBER" and random.random() < 0.4,
                "created_at": (NOW - timedelta(days=random.randint(0, 14))).isoformat(),
            })

    batch_insert("alerts", alert_rows)

    # 7. Intervention logs for actioned alerts
    print("  → Logging interventions...")
    actioned = [a for a in alert_rows if a["actioned"]]
    intervention_rows = []
    for a in actioned:
        mentor_id = next(s["mentor_id"] for s in students if s["id"] == a["student_id"])
        mentor    = next(m for m in MENTORS if m["id"] == mentor_id)
        intervention_rows.append({
            "id": uid(),
            "alert_id":    a["id"],
            "student_id":  a["student_id"],
            "mentor_id":   mentor_id,
            "mentor_name": mentor["name"],
            "notes": "Follow-up meeting scheduled. Student agreed to attend additional support sessions.",
            "logged_at": (NOW - timedelta(days=random.randint(0, 7))).isoformat(),
        })

    if intervention_rows:
        batch_insert("intervention_logs", intervention_rows)

    # 8. Cohort snapshots
    print("  → Building cohort snapshots...")
    snapshot_rows = []
    for i, week in enumerate(weeks()):
        # Simulate improving trajectory overall
        week_students = []
        for s in students:
            sig = (gen_red_signals(i) if s["id"] in red_ids
                   else gen_amber_signals(i) if s["id"] in amber_ids
                   else gen_green_signals(i))
            score, _ = score_student(sig, 0)
            week_students.append(score)

        avg = round(sum(week_students) / len(week_students), 2)
        red_c   = sum(1 for sc in week_students if sc >= 70)
        amber_c = sum(1 for sc in week_students if 45 <= sc < 70)
        green_c = len(week_students) - red_c - amber_c

        snapshot_rows.append({
            "id": uid(),
            "week": week,
            "avg_risk_score": avg,
            "red_count": red_c,
            "amber_count": amber_c,
            "green_count": green_c,
        })

    batch_insert("cohort_snapshots", snapshot_rows)

    print("\n✅ Seed complete!")
    print(f"   Mentors:       {len(MENTORS)}")
    print(f"   Students:      {len(students)}")
    print(f"     RED:         {len(red_ids)}")
    print(f"     AMBER:       {len(amber_ids)}")
    print(f"     GREEN:       {50 - len(red_ids) - len(amber_ids)}")
    print(f"   Alerts:        {len(alert_rows)}")
    print(f"   Interventions: {len(intervention_rows)}")
    print(f"   Weeks of data: {len(weeks())}")
    print("\nDemo login credentials:")
    print("  admin@academiq.demo  / admin123")
    print("  mentor@academiq.demo / mentor123")
    print("  student@academiq.demo / student123")


if __name__ == "__main__":
    seed()
