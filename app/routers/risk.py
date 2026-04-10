import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_mentor, require_admin, TokenData
from app.db.supabase import get_supabase
from app.models.schemas import RiskSignals, RiskResult, BulkRiskRequest
from app.services.risk_engine import compute_risk_score
from app.services.alerts_service import send_red_alert_email

router = APIRouter(prefix="/risk", tags=["risk"])


def _build_signals_from_db(student_id: str, db) -> RiskSignals:
    """Pull latest data rows for a student and build a RiskSignals object."""
    att = db.table("attendance_records").select("attendance_pct") \
        .eq("student_id", student_id).order("week", desc=True).limit(1).execute()
    grade = db.table("grade_records").select("grade") \
        .eq("student_id", student_id).order("week", desc=True).limit(1).execute()
    eng = db.table("engagement_records").select("lms_logins, assignment_submissions") \
        .eq("student_id", student_id).order("week", desc=True).limit(1).execute()
    sent = db.table("sentiment_records").select("sentiment_score") \
        .eq("student_id", student_id).order("week", desc=True).limit(1).execute()
    surveys = db.table("surveys").select("week") \
        .eq("student_id", student_id).order("week", desc=True).limit(1).execute()

    current_week = datetime.now(timezone.utc).isocalendar()[1]
    last_survey_week = surveys.data[0]["week"] if surveys.data else 0
    missed = max(0, current_week - last_survey_week - 1)

    submissions = eng.data[0].get("assignment_submissions", 5) if eng.data else 5

    return RiskSignals(
        attendance_pct=att.data[0]["attendance_pct"] if att.data else 100.0,
        grade_avg=grade.data[0]["grade"] if grade.data else 100.0,
        lms_logins_week=eng.data[0].get("lms_logins", 10) if eng.data else 10,
        assignment_completion_pct=min(100.0, (submissions / 5) * 100),
        sentiment_score=sent.data[0]["sentiment_score"] if sent.data else 0.0,
        missed_surveys=missed,
    )


async def _rescore_and_alert(student_id: str, db) -> RiskResult:
    """Rescore a single student and create an alert if they cross RED/AMBER threshold."""

    student_res = db.table("students").select("*, mentors(name, email)") \
        .eq("id", student_id).single().execute()
    if not student_res.data:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    student = student_res.data
    prev_tier = student.get("risk_tier", "GREEN")

    signals = _build_signals_from_db(student_id, db)
    result = compute_risk_score(signals)

    now = datetime.now(timezone.utc).isoformat()

    # Persist updated score
    db.table("students").update({
        "risk_score": result.total_score,
        "risk_tier": result.tier,
        "last_updated": now,
    }).eq("id", student_id).execute()

    alert_created = False

    # Create alert if tier worsened to AMBER or RED
    tier_order = {"GREEN": 0, "AMBER": 1, "RED": 2}
    if tier_order.get(result.tier, 0) > tier_order.get(prev_tier, 0):
        trigger = _build_trigger_text(signals, result)

        alert_id = str(uuid.uuid4())
        db.table("alerts").insert({
            "id": alert_id,
            "student_id": student_id,
            "severity": result.tier,
            "trigger": trigger,
            "actioned": False,
            "created_at": now,
        }).execute()
        alert_created = True

        # Send immediate email for RED alerts
        if result.tier == "RED":
            mentor = student.get("mentors") or {}
            if isinstance(mentor, dict) and mentor.get("email"):
                send_red_alert_email(
                    mentor_email=mentor["email"],
                    mentor_name=mentor.get("name", "Mentor"),
                    student_name=student["name"],
                    student_id=student_id,
                    risk_score=result.total_score,
                    trigger=trigger,
                )

    return RiskResult(
        student_id=student_id,
        risk_score=result.total_score,
        risk_tier=result.tier,
        signal_breakdown=result.breakdown,
        alert_created=alert_created,
    )


def _build_trigger_text(signals: RiskSignals, result) -> str:
    """Build a human-readable trigger description from the highest-contributing signals."""
    bd = result.breakdown
    sorted_signals = sorted(bd.items(), key=lambda x: x[1]["weighted_contribution"], reverse=True)
    top = sorted_signals[0][0] if sorted_signals else "multiple signals"

    label_map = {
        "attendance": f"Attendance dropped to {signals.attendance_pct:.0f}%",
        "grade": f"Grade average fell to {signals.grade_avg:.0f}%",
        "lms": f"LMS logins this week: {signals.lms_logins_week}",
        "assignments": f"Assignment completion at {signals.assignment_completion_pct:.0f}%",
        "sentiment": f"Negative sentiment score ({signals.sentiment_score:.2f})",
        "surveys": f"{signals.missed_surveys} consecutive survey(s) missed",
    }

    return label_map.get(top, "Multiple risk indicators elevated")


@router.post("/rescore/{student_id}", response_model=RiskResult)
async def rescore_student(
    student_id: str,
    current_user: TokenData = Depends(require_mentor),
):
    """Manually trigger a risk rescore for one student."""
    db = get_supabase()
    return await _rescore_and_alert(student_id, db)


@router.post("/rescore/bulk", response_model=list[RiskResult])
async def bulk_rescore(
    body: BulkRiskRequest,
    current_user: TokenData = Depends(require_admin),
):
    """Admin: rescore a list of students in one call."""
    db = get_supabase()
    results = []
    for sid in body.student_ids:
        try:
            r = await _rescore_and_alert(sid, db)
            results.append(r)
        except HTTPException:
            pass  # Skip missing students silently in bulk
    return results


@router.post("/rescore/all", response_model=dict)
async def rescore_all(current_user: TokenData = Depends(require_admin)):
    """Admin: rescore every student in the system."""
    db = get_supabase()
    all_students = db.table("students").select("id").execute().data or []
    ids = [s["id"] for s in all_students]

    results = []
    for sid in ids:
        try:
            r = await _rescore_and_alert(sid, db)
            results.append(r)
        except Exception:
            pass

    red = sum(1 for r in results if r.risk_tier == "RED")
    amber = sum(1 for r in results if r.risk_tier == "AMBER")
    alerts = sum(1 for r in results if r.alert_created)

    return {
        "rescored": len(results),
        "red": red,
        "amber": amber,
        "green": len(results) - red - amber,
        "alerts_created": alerts,
    }
