import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_any, TokenData
from app.db.supabase import get_supabase
from app.models.schemas import SurveySubmitRequest, SurveySubmitResponse, RiskSignals
from app.services.sentiment import analyse_sentiment
from app.services.risk_engine import compute_risk_score

router = APIRouter(prefix="/surveys", tags=["surveys"])

PULSE_QUESTIONS = [
    "How are you feeling about your studies this week?",
    "Have you been able to keep up with your coursework?",
    "How would you describe your motivation and energy levels?",
    "Is there anything making university life difficult right now?",
    "How supported do you feel by your mentor and institution?",
]


@router.get("/questions")
async def get_questions():
    """Return the current pulse survey questions."""
    return {"questions": PULSE_QUESTIONS}


@router.post("/submit", response_model=SurveySubmitResponse)
async def submit_survey(
    body: SurveySubmitRequest,
    current_user: TokenData = Depends(require_any),
):
    """
    Submit pulse survey responses.
    1. Runs Claude sentiment analysis on responses.
    2. Stores the survey record.
    3. Rescores student risk incorporating new sentiment.
    4. Returns updated risk values.
    """
    db = get_supabase()

    # Verify student exists
    student_res = db.table("students").select("*").eq("id", body.student_id).single().execute()
    if not student_res.data:
        raise HTTPException(status_code=404, detail="Student not found")

    student = student_res.data

    # 1. Sentiment analysis
    sentiment = await analyse_sentiment(body.responses)

    # 2. Store survey
    survey_id = str(uuid.uuid4())
    week = body.week or _current_week()
    now = datetime.now(timezone.utc).isoformat()

    db.table("surveys").insert({
        "id": survey_id,
        "student_id": body.student_id,
        "week": week,
        "responses": body.responses,
        "sentiment_score": sentiment["score"],
        "sentiment_label": sentiment["label"],
        "sentiment_summary": sentiment.get("summary", ""),
        "submitted_at": now,
    }).execute()

    # Store sentiment record for trend
    db.table("sentiment_records").upsert({
        "student_id": body.student_id,
        "week": week,
        "sentiment_score": sentiment["score"],
    }).execute()

    # 3. Rescore risk
    # Fetch latest signals for this student
    att_res = db.table("attendance_records").select("attendance_pct") \
        .eq("student_id", body.student_id).order("week", desc=True).limit(1).execute()
    grade_res = db.table("grade_records").select("grade") \
        .eq("student_id", body.student_id).order("week", desc=True).limit(1).execute()
    eng_res = db.table("engagement_records").select("lms_logins, assignment_submissions") \
        .eq("student_id", body.student_id).order("week", desc=True).limit(1).execute()
    survey_count_res = db.table("surveys").select("id") \
        .eq("student_id", body.student_id).execute()

    att = (att_res.data[0]["attendance_pct"] if att_res.data else 100.0)
    grade = (grade_res.data[0]["grade"] if grade_res.data else 100.0)
    logins = (eng_res.data[0]["lms_logins"] if eng_res.data else 10)
    submissions = (eng_res.data[0]["assignment_submissions"] if eng_res.data else 5)
    total_surveys = len(survey_count_res.data or [])
    missed = max(0, week - total_surveys)

    signals = RiskSignals(
        attendance_pct=att,
        grade_avg=grade,
        lms_logins_week=logins,
        assignment_completion_pct=min(100.0, (submissions / 5) * 100),
        sentiment_score=sentiment["score"],
        missed_surveys=missed,
    )

    result = compute_risk_score(signals)

    # Update student risk score
    db.table("students").update({
        "risk_score": result.total_score,
        "risk_tier": result.tier,
        "last_updated": now,
    }).eq("id", body.student_id).execute()

    return SurveySubmitResponse(
        survey_id=survey_id,
        sentiment_score=sentiment["score"],
        sentiment_label=sentiment["label"],
        risk_rescored=True,
        new_risk_score=result.total_score,
        new_risk_tier=result.tier,
    )


def _current_week() -> int:
    """Return current ISO week number."""
    return datetime.now(timezone.utc).isocalendar()[1]
