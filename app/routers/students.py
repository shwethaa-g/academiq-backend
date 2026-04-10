from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.core.security import require_mentor, require_any, TokenData
from app.db.supabase import get_supabase
from app.models.schemas import (
    StudentListResponse, StudentSummary, StudentProfile,
    AttendanceRecord, GradeRecord, EngagementRecord, SentimentRecord,
)

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=StudentListResponse)
async def list_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    risk_tier: Optional[str] = Query(None, pattern="^(RED|AMBER|GREEN)$"),
    mentor_id: Optional[str] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(require_mentor),
):
    """List students with optional filtering by tier, mentor, or name search."""
    db = get_supabase()

    query = db.table("students").select(
        "id, name, email, mentor_id, risk_score, risk_tier, last_updated, mentors(name)"
    )

    # Mentors can only see their own cohort
    if current_user.role == "mentor":
        query = query.eq("mentor_id", current_user.sub)
    elif mentor_id:
        query = query.eq("mentor_id", mentor_id)

    if risk_tier:
        query = query.eq("risk_tier", risk_tier)

    if search:
        query = query.ilike("name", f"%{search}%")

    # Get total count
    count_res = query.execute()
    total = len(count_res.data)

    # Paginate
    offset = (page - 1) * page_size
    result = query.order("risk_score", desc=True).range(offset, offset + page_size - 1).execute()

    students = []
    for row in result.data:
        mentor_data = row.get("mentors") or {}
        students.append(StudentSummary(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            mentor_id=row.get("mentor_id"),
            mentor_name=mentor_data.get("name") if isinstance(mentor_data, dict) else None,
            risk_score=row.get("risk_score", 0),
            risk_tier=row.get("risk_tier", "GREEN"),
            last_updated=row.get("last_updated"),
        ))

    return StudentListResponse(students=students, total=total, page=page, page_size=page_size)


@router.get("/{student_id}", response_model=StudentProfile)
async def get_student_profile(
    student_id: str,
    current_user: TokenData = Depends(require_any),
):
    """Get full student profile including all trend data."""
    db = get_supabase()

    # Fetch student base record
    res = db.table("students").select(
        "*, mentors(name)"
    ).eq("id", student_id).single().execute()

    if not res.data:
        raise HTTPException(status_code=404, detail="Student not found")

    row = res.data
    mentor_data = row.get("mentors") or {}

    # Access control: students can only see their own profile
    if current_user.role == "student" and current_user.sub != student_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Fetch trend data
    att_res = db.table("attendance_records").select("week, attendance_pct") \
        .eq("student_id", student_id).order("week").execute()

    grade_res = db.table("grade_records").select("week, grade") \
        .eq("student_id", student_id).order("week").execute()

    eng_res = db.table("engagement_records") \
        .select("week, lms_logins, assignment_submissions, forum_posts") \
        .eq("student_id", student_id).order("week").execute()

    sent_res = db.table("sentiment_records").select("week, sentiment_score") \
        .eq("student_id", student_id).order("week").execute()

    return StudentProfile(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        programme=row.get("programme", ""),
        year=row.get("year", 1),
        mentor_id=row.get("mentor_id"),
        mentor_name=mentor_data.get("name") if isinstance(mentor_data, dict) else None,
        risk_score=row.get("risk_score", 0),
        risk_tier=row.get("risk_tier", "GREEN"),
        last_updated=row.get("last_updated"),
        attendance_trend=[AttendanceRecord(**r) for r in (att_res.data or [])],
        grade_trend=[GradeRecord(**r) for r in (grade_res.data or [])],
        engagement_trend=[EngagementRecord(**r) for r in (eng_res.data or [])],
        sentiment_trend=[SentimentRecord(**r) for r in (sent_res.data or [])],
    )
