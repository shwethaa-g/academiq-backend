from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta

from app.core.security import require_admin, require_mentor, TokenData
from app.db.supabase import get_supabase
from app.models.schemas import (
    AdminStatsOut, MentorStatsOut, CohortTrendPoint, AlertVolumePoint
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/admin/stats", response_model=AdminStatsOut)
async def admin_stats(current_user: TokenData = Depends(require_admin)):
    """High-level stats for the admin dashboard."""
    db = get_supabase()

    students = db.table("students").select("risk_tier").execute().data or []
    alerts = db.table("alerts").select("id").eq("actioned", False).execute().data or []

    today = datetime.now(timezone.utc).date().isoformat()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    interventions = db.table("intervention_logs").select("id") \
        .gte("logged_at", week_ago).execute().data or []

    return AdminStatsOut(
        total_students=len(students),
        red_count=sum(1 for s in students if s["risk_tier"] == "RED"),
        amber_count=sum(1 for s in students if s["risk_tier"] == "AMBER"),
        green_count=sum(1 for s in students if s["risk_tier"] == "GREEN"),
        active_alerts=len(alerts),
        interventions_this_week=len(interventions),
    )


@router.get("/mentor/stats")
async def mentor_stats(current_user: TokenData = Depends(require_mentor)):
    """Stats for a mentor's own cohort."""
    db = get_supabase()

    mentor_id = current_user.sub
    students = db.table("students").select("risk_tier") \
        .eq("mentor_id", mentor_id).execute().data or []

    mentor_res = db.table("mentors").select("name").eq("id", mentor_id).execute()
    mentor_name = mentor_res.data[0]["name"] if mentor_res.data else current_user.name

    return MentorStatsOut(
        mentor_id=mentor_id,
        mentor_name=mentor_name,
        total_students=len(students),
        red_count=sum(1 for s in students if s["risk_tier"] == "RED"),
        amber_count=sum(1 for s in students if s["risk_tier"] == "AMBER"),
        green_count=sum(1 for s in students if s["risk_tier"] == "GREEN"),
    )


@router.get("/cohort/trends")
async def cohort_trends(current_user: TokenData = Depends(require_mentor)):
    """Weekly cohort-level risk trend data for charts."""
    db = get_supabase()

    res = db.table("cohort_snapshots").select("*").order("week").execute()
    rows = res.data or []

    return [
        CohortTrendPoint(
            week=r["week"],
            avg_risk_score=r.get("avg_risk_score", 0),
            red_count=r.get("red_count", 0),
            amber_count=r.get("amber_count", 0),
            green_count=r.get("green_count", 0),
        )
        for r in rows
    ]


@router.get("/alerts/volume")
async def alert_volume(current_user: TokenData = Depends(require_mentor)):
    """Daily alert volume for the past 30 days."""
    db = get_supabase()

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    res = db.table("alerts").select("severity, created_at").gte("created_at", since).execute()
    rows = res.data or []

    # Group by date
    volume: dict[str, dict] = {}
    for r in rows:
        day = r["created_at"][:10]
        if day not in volume:
            volume[day] = {"red_alerts": 0, "amber_alerts": 0}
        if r["severity"] == "RED":
            volume[day]["red_alerts"] += 1
        else:
            volume[day]["amber_alerts"] += 1

    return [
        AlertVolumePoint(date=d, **v)
        for d, v in sorted(volume.items())
    ]


@router.get("/mentors/overview")
async def all_mentor_stats(current_user: TokenData = Depends(require_admin)):
    """Admin view: stats for every mentor."""
    db = get_supabase()

    mentors = db.table("mentors").select("id, name").execute().data or []
    students = db.table("students").select("mentor_id, risk_tier").execute().data or []

    result = []
    for m in mentors:
        cohort = [s for s in students if s["mentor_id"] == m["id"]]
        result.append(MentorStatsOut(
            mentor_id=m["id"],
            mentor_name=m["name"],
            total_students=len(cohort),
            red_count=sum(1 for s in cohort if s["risk_tier"] == "RED"),
            amber_count=sum(1 for s in cohort if s["risk_tier"] == "AMBER"),
            green_count=sum(1 for s in cohort if s["risk_tier"] == "GREEN"),
        ))

    return result
