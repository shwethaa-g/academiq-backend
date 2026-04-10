"""
Alert email service using Resend.
- RED alerts: immediate HTML email to mentor
- AMBER alerts: queued for daily digest (sent in batch)
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import List

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _init_resend():
    resend.api_key = settings.RESEND_API_KEY


# ── RED — Immediate alert ─────────────────────────────────────────────────────

def send_red_alert_email(
    mentor_email: str,
    mentor_name: str,
    student_name: str,
    student_id: str,
    risk_score: float,
    trigger: str,
    dashboard_url: str = "https://academiq.app/alerts",
) -> bool:
    """Send an immediate RED alert email to the assigned mentor."""
    _init_resend()

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background:#f4f4f5; margin:0; padding:32px; }}
    .card {{ background:#fff; border-radius:12px; max-width:560px; margin:0 auto;
             overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
    .header {{ background:#dc2626; padding:24px 32px; }}
    .header h1 {{ color:#fff; margin:0; font-size:20px; font-weight:700; }}
    .header p  {{ color:#fecaca; margin:4px 0 0; font-size:14px; }}
    .body {{ padding:32px; }}
    .student-box {{ background:#fef2f2; border:1px solid #fecaca;
                   border-radius:8px; padding:16px 20px; margin-bottom:24px; }}
    .student-box h2 {{ margin:0 0 4px; font-size:18px; color:#111; }}
    .student-box p  {{ margin:0; color:#6b7280; font-size:14px; }}
    .score {{ font-size:36px; font-weight:800; color:#dc2626; }}
    .trigger {{ background:#fff7ed; border:1px solid #fed7aa;
                border-radius:6px; padding:12px 16px; margin:16px 0;
                font-size:14px; color:#7c3aed; }}
    .btn {{ display:inline-block; background:#dc2626; color:#fff;
            padding:12px 24px; border-radius:8px; text-decoration:none;
            font-weight:600; font-size:14px; margin-top:16px; }}
    .footer {{ color:#9ca3af; font-size:12px; padding:16px 32px;
               border-top:1px solid #f3f4f6; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>🚨 Immediate Action Required</h1>
      <p>AcademIQ Early Warning System</p>
    </div>
    <div class="body">
      <div class="student-box">
        <h2>{student_name}</h2>
        <p>Student ID: {student_id}</p>
      </div>
      <p style="margin:0 0 4px; color:#6b7280; font-size:13px; text-transform:uppercase;
                letter-spacing:.05em; font-weight:600;">Current Risk Score</p>
      <div class="score">{risk_score:.0f} / 100</div>
      <div class="trigger">
        <strong>Trigger:</strong> {trigger}
      </div>
      <p style="color:#374151; font-size:15px;">
        Hi {mentor_name}, this student has entered the <strong>RED risk tier</strong>
        and requires your immediate attention. Please reach out as soon as possible.
      </p>
      <a href="{dashboard_url}" class="btn">View Student Dashboard →</a>
    </div>
    <div class="footer">
      AcademIQ · {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC ·
      You are receiving this because you are the assigned mentor.
    </div>
  </div>
</body>
</html>
"""

    try:
        resend.Emails.send({
            "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
            "to": [mentor_email],
            "subject": f"🚨 URGENT: {student_name} requires immediate support",
            "html": html,
        })
        logger.info(f"RED alert email sent to {mentor_email} for student {student_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send RED alert email: {e}")
        return False


# ── AMBER — Daily digest ─────────────────────────────────────────────────────

def send_amber_digest_email(
    mentor_email: str,
    mentor_name: str,
    students: List[dict],   # [{name, id, risk_score, trigger}, ...]
    dashboard_url: str = "https://academiq.app/alerts",
) -> bool:
    """Send a daily AMBER digest email listing all at-risk students."""
    _init_resend()

    if not students:
        return False

    rows = ""
    for s in students:
        rows += f"""
        <tr>
          <td style="padding:10px 12px; border-bottom:1px solid #f3f4f6;">{s['name']}</td>
          <td style="padding:10px 12px; border-bottom:1px solid #f3f4f6;
                     text-align:center; font-weight:600; color:#d97706;">{s['risk_score']:.0f}</td>
          <td style="padding:10px 12px; border-bottom:1px solid #f3f4f6;
                     color:#6b7280; font-size:13px;">{s.get('trigger', '—')}</td>
        </tr>"""

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
           background:#f4f4f5; margin:0; padding:32px; }}
    .card {{ background:#fff; border-radius:12px; max-width:600px; margin:0 auto;
             overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
    .header {{ background:#d97706; padding:24px 32px; }}
    .header h1 {{ color:#fff; margin:0; font-size:20px; font-weight:700; }}
    .header p  {{ color:#fde68a; margin:4px 0 0; font-size:14px; }}
    .body {{ padding:32px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th {{ text-align:left; padding:10px 12px; background:#f9fafb;
          font-size:12px; text-transform:uppercase; letter-spacing:.05em;
          color:#6b7280; font-weight:600; }}
    .btn {{ display:inline-block; background:#d97706; color:#fff;
            padding:12px 24px; border-radius:8px; text-decoration:none;
            font-weight:600; font-size:14px; margin-top:24px; }}
    .footer {{ color:#9ca3af; font-size:12px; padding:16px 32px;
               border-top:1px solid #f3f4f6; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>⚠️ Daily AMBER Alert Digest</h1>
      <p>{datetime.utcnow().strftime('%A, %d %B %Y')} · AcademIQ</p>
    </div>
    <div class="body">
      <p style="color:#374151;">Hi {mentor_name}, here are your students currently
         in the <strong>AMBER risk tier</strong> that may need follow-up today:</p>
      <table>
        <thead>
          <tr>
            <th>Student</th>
            <th style="text-align:center">Risk Score</th>
            <th>Trigger</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <a href="{dashboard_url}" class="btn">View All Alerts →</a>
    </div>
    <div class="footer">
      AcademIQ · You are receiving this digest as the assigned mentor.
    </div>
  </div>
</body>
</html>
"""

    try:
        resend.Emails.send({
            "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
            "to": [mentor_email],
            "subject": f"⚠️ Daily Digest: {len(students)} student(s) need your attention",
            "html": html,
        })
        logger.info(f"AMBER digest sent to {mentor_email} ({len(students)} students)")
        return True
    except Exception as e:
        logger.error(f"Failed to send AMBER digest: {e}")
        return False
