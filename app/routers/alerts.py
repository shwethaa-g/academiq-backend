from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone

from app.core.security import require_mentor, require_any, TokenData
from app.db.supabase import get_supabase
from app.models.schemas import AlertListResponse, AlertOut, AlertActionRequest, AlertStatsOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    severity: Optional[str] = Query(None, pattern="^(RED|AMBER)$"),
    actioned: Optional[bool] = None,
    mentor_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(require_mentor),
):
    """List alerts, optionally filtered by severity, actioned status, or mentor."""
    db = get_supabase()

    query = db.table("alerts").select(
        "*, students(name, mentor_id)"
    ).order("created_at", desc=True)

    if current_user.role == "mentor":
        # Join through students to filter by mentor
        query = query.eq("students.mentor_id", current_user.sub)

    if severity:
        query = query.eq("severity", severity)

    if actioned is not None:
        query = query.eq("actioned", actioned)

    result = query.execute()
    data = result.data or []
    total = len(data)

    offset = (page - 1) * page_size
    page_data = data[offset: offset + page_size]

    alerts = []
    for row in page_data:
        student = row.get("students") or {}
        alerts.append(AlertOut(
            id=row["id"],
            student_id=row["student_id"],
            student_name=student.get("name", "Unknown") if isinstance(student, dict) else "Unknown",
            severity=row["severity"],
            trigger=row.get("trigger", ""),
            created_at=row["created_at"],
            actioned=row.get("actioned", False),
            actioned_at=row.get("actioned_at"),
            actioned_by=row.get("actioned_by"),
            notes=row.get("notes"),
        ))

    return AlertListResponse(alerts=alerts, total=total)


@router.post("/{alert_id}/action")
async def action_alert(
    alert_id: str,
    body: AlertActionRequest,
    current_user: TokenData = Depends(require_mentor),
):
    """Mark an alert as actioned and log the intervention."""
    db = get_supabase()

    # Verify alert exists
    res = db.table("alerts").select("*").eq("id", alert_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(timezone.utc).isoformat()

    # Update alert
    db.table("alerts").update({
        "actioned": True,
        "actioned_at": now,
        "actioned_by": current_user.name,
        "notes": body.notes,
    }).eq("id", alert_id).execute()

    # Log intervention
    db.table("intervention_logs").insert({
        "alert_id": alert_id,
        "student_id": res.data["student_id"],
        "mentor_id": current_user.sub,
        "mentor_name": current_user.name,
        "notes": body.notes,
        "logged_at": now,
    }).execute()

    return {"message": "Alert actioned successfully", "alert_id": alert_id}


@router.get("/stats", response_model=AlertStatsOut)
async def alert_stats(
    current_user: TokenData = Depends(require_mentor),
):
    """Summary stats for the alerts dashboard."""
    db = get_supabase()

    all_res = db.table("alerts").select("severity, actioned, actioned_at").execute()
    rows = all_res.data or []

    today = datetime.now(timezone.utc).date().isoformat()

    total_active = sum(1 for r in rows if not r["actioned"])
    red_count = sum(1 for r in rows if not r["actioned"] and r["severity"] == "RED")
    amber_count = sum(1 for r in rows if not r["actioned"] and r["severity"] == "AMBER")
    actioned_today = sum(
        1 for r in rows
        if r["actioned"] and r.get("actioned_at", "")[:10] == today
    )

    return AlertStatsOut(
        total_active=total_active,
        red_count=red_count,
        amber_count=amber_count,
        actioned_today=actioned_today,
    )
