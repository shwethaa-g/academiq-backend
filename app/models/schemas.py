from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ── Auth ────────────────────────────────────────────────────────────────────

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


# ── Mentor ──────────────────────────────────────────────────────────────────

class MentorOut(BaseModel):
    id: str
    name: str
    email: str
    student_count: Optional[int] = 0


# ── Student ─────────────────────────────────────────────────────────────────

class StudentSummary(BaseModel):
    id: str
    name: str
    email: str
    mentor_id: Optional[str] = None
    mentor_name: Optional[str] = None
    risk_score: float
    risk_tier: str          # GREEN | AMBER | RED
    last_updated: Optional[datetime] = None


class AttendanceRecord(BaseModel):
    week: int
    attendance_pct: float


class GradeRecord(BaseModel):
    week: int
    grade: float


class EngagementRecord(BaseModel):
    week: int
    lms_logins: int
    assignment_submissions: int
    forum_posts: int


class SentimentRecord(BaseModel):
    week: int
    sentiment_score: float   # -1.0 to 1.0


class StudentProfile(BaseModel):
    id: str
    name: str
    email: str
    programme: str
    year: int
    mentor_id: Optional[str] = None
    mentor_name: Optional[str] = None
    risk_score: float
    risk_tier: str
    last_updated: Optional[datetime] = None
    attendance_trend: List[AttendanceRecord] = []
    grade_trend: List[GradeRecord] = []
    engagement_trend: List[EngagementRecord] = []
    sentiment_trend: List[SentimentRecord] = []


class StudentListResponse(BaseModel):
    students: List[StudentSummary]
    total: int
    page: int
    page_size: int


# ── Alerts ──────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    student_id: str
    student_name: str
    severity: str            # RED | AMBER
    trigger: str
    created_at: datetime
    actioned: bool
    actioned_at: Optional[datetime] = None
    actioned_by: Optional[str] = None
    notes: Optional[str] = None


class AlertActionRequest(BaseModel):
    notes: Optional[str] = None


class AlertStatsOut(BaseModel):
    total_active: int
    red_count: int
    amber_count: int
    actioned_today: int


class AlertListResponse(BaseModel):
    alerts: List[AlertOut]
    total: int


# ── Surveys ─────────────────────────────────────────────────────────────────

class SurveySubmitRequest(BaseModel):
    student_id: str
    responses: List[str]        # free-text answers to pulse questions
    week: Optional[int] = None


class SurveySubmitResponse(BaseModel):
    survey_id: str
    sentiment_score: float
    sentiment_label: str        # positive | neutral | negative
    risk_rescored: bool
    new_risk_score: Optional[float] = None
    new_risk_tier: Optional[str] = None


# ── Risk ────────────────────────────────────────────────────────────────────

class RiskSignals(BaseModel):
    attendance_pct: float = 100.0
    grade_avg: float = 100.0
    lms_logins_week: int = 10
    assignment_completion_pct: float = 100.0
    sentiment_score: float = 0.0    # -1.0 to 1.0
    missed_surveys: int = 0


class RiskResult(BaseModel):
    student_id: str
    risk_score: float
    risk_tier: str
    signal_breakdown: dict
    alert_created: bool = False


class BulkRiskRequest(BaseModel):
    student_ids: List[str]


# ── Reports ─────────────────────────────────────────────────────────────────

class AdminStatsOut(BaseModel):
    total_students: int
    red_count: int
    amber_count: int
    green_count: int
    active_alerts: int
    interventions_this_week: int


class MentorStatsOut(BaseModel):
    mentor_id: str
    mentor_name: str
    total_students: int
    red_count: int
    amber_count: int
    green_count: int


class CohortTrendPoint(BaseModel):
    week: int
    avg_risk_score: float
    red_count: int
    amber_count: int
    green_count: int


class AlertVolumePoint(BaseModel):
    date: str
    red_alerts: int
    amber_alerts: int
