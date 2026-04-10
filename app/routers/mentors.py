from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_admin, require_mentor, TokenData
from app.db.supabase import get_supabase
from app.models.schemas import MentorOut, StudentSummary

router = APIRouter(prefix="/mentors", tags=["mentors"])


@router.get("", response_model=list[MentorOut])
async def list_mentors(current_user: TokenData = Depends(require_admin)):
    """Admin only: list all mentors with student counts."""
    db = get_supabase()

    mentors = db.table("mentors").select("id, name, email").execute().data or []
    students = db.table("students").select("mentor_id").execute().data or []

    counts: dict[str, int] = {}
    for s in students:
        mid = s.get("mentor_id")
        if mid:
            counts[mid] = counts.get(mid, 0) + 1

    return [
        MentorOut(
            id=m["id"],
            name=m["name"],
            email=m["email"],
            student_count=counts.get(m["id"], 0),
        )
        for m in mentors
    ]


@router.get("/{mentor_id}/students", response_model=list[StudentSummary])
async def mentor_students(
    mentor_id: str,
    current_user: TokenData = Depends(require_mentor),
):
    """List all students assigned to a mentor."""
    db = get_supabase()

    # Mentors can only query their own cohort
    if current_user.role == "mentor" and current_user.sub != mentor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    res = db.table("students").select(
        "id, name, email, mentor_id, risk_score, risk_tier, last_updated, mentors(name)"
    ).eq("mentor_id", mentor_id).order("risk_score", desc=True).execute()

    students = []
    for row in (res.data or []):
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

    return students


@router.get("/me/students", response_model=list[StudentSummary])
async def my_students(current_user: TokenData = Depends(require_mentor)):
    """Shortcut: mentor's own student list using JWT identity."""
    db = get_supabase()

    res = db.table("students").select(
        "id, name, email, mentor_id, risk_score, risk_tier, last_updated, mentors(name)"
    ).eq("mentor_id", current_user.sub).order("risk_score", desc=True).execute()

    students = []
    for row in (res.data or []):
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

    return students
