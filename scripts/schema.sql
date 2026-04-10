-- ============================================================
--  AcademIQ — Supabase Schema
--  Run once in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";

-- ── mentors ──────────────────────────────────────────────────

create table if not exists mentors (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  email       text not null unique,
  created_at  timestamptz default now()
);

-- ── students ─────────────────────────────────────────────────

create table if not exists students (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  email         text not null unique,
  programme     text not null default 'BSc Computer Science',
  year          int  not null default 1,
  mentor_id     uuid references mentors(id) on delete set null,
  risk_score    numeric(5,2) not null default 0,
  risk_tier     text not null default 'GREEN'
                  check (risk_tier in ('GREEN','AMBER','RED')),
  last_updated  timestamptz default now(),
  created_at    timestamptz default now()
);

create index if not exists idx_students_mentor_id  on students(mentor_id);
create index if not exists idx_students_risk_tier  on students(risk_tier);
create index if not exists idx_students_risk_score on students(risk_score desc);

-- ── attendance_records ───────────────────────────────────────

create table if not exists attendance_records (
  id              uuid primary key default gen_random_uuid(),
  student_id      uuid not null references students(id) on delete cascade,
  week            int  not null,
  attendance_pct  numeric(5,2) not null default 100,
  recorded_at     timestamptz default now(),
  unique(student_id, week)
);

create index if not exists idx_att_student_week on attendance_records(student_id, week desc);

-- ── grade_records ────────────────────────────────────────────

create table if not exists grade_records (
  id          uuid primary key default gen_random_uuid(),
  student_id  uuid not null references students(id) on delete cascade,
  week        int  not null,
  grade       numeric(5,2) not null default 100,
  recorded_at timestamptz default now(),
  unique(student_id, week)
);

create index if not exists idx_grade_student_week on grade_records(student_id, week desc);

-- ── engagement_records ───────────────────────────────────────

create table if not exists engagement_records (
  id                       uuid primary key default gen_random_uuid(),
  student_id               uuid not null references students(id) on delete cascade,
  week                     int  not null,
  lms_logins               int  not null default 0,
  assignment_submissions   int  not null default 0,
  forum_posts              int  not null default 0,
  recorded_at              timestamptz default now(),
  unique(student_id, week)
);

create index if not exists idx_eng_student_week on engagement_records(student_id, week desc);

-- ── sentiment_records ────────────────────────────────────────

create table if not exists sentiment_records (
  id               uuid primary key default gen_random_uuid(),
  student_id       uuid not null references students(id) on delete cascade,
  week             int  not null,
  sentiment_score  numeric(4,3) not null default 0,
  recorded_at      timestamptz default now(),
  unique(student_id, week)
);

create index if not exists idx_sent_student_week on sentiment_records(student_id, week desc);

-- ── surveys ──────────────────────────────────────────────────

create table if not exists surveys (
  id                  uuid primary key default gen_random_uuid(),
  student_id          uuid not null references students(id) on delete cascade,
  week                int  not null,
  responses           text[] not null default '{}',
  sentiment_score     numeric(4,3) not null default 0,
  sentiment_label     text not null default 'neutral',
  sentiment_summary   text,
  submitted_at        timestamptz default now()
);

create index if not exists idx_surveys_student on surveys(student_id, week desc);

-- ── alerts ───────────────────────────────────────────────────

create table if not exists alerts (
  id           uuid primary key default gen_random_uuid(),
  student_id   uuid not null references students(id) on delete cascade,
  severity     text not null check (severity in ('RED','AMBER')),
  trigger      text not null,
  actioned     boolean not null default false,
  actioned_at  timestamptz,
  actioned_by  text,
  notes        text,
  created_at   timestamptz default now()
);

create index if not exists idx_alerts_student    on alerts(student_id);
create index if not exists idx_alerts_severity   on alerts(severity);
create index if not exists idx_alerts_actioned   on alerts(actioned);
create index if not exists idx_alerts_created_at on alerts(created_at desc);

-- ── intervention_logs ────────────────────────────────────────

create table if not exists intervention_logs (
  id           uuid primary key default gen_random_uuid(),
  alert_id     uuid references alerts(id) on delete set null,
  student_id   uuid not null references students(id) on delete cascade,
  mentor_id    uuid references mentors(id) on delete set null,
  mentor_name  text,
  notes        text,
  logged_at    timestamptz default now()
);

create index if not exists idx_interventions_student on intervention_logs(student_id);
create index if not exists idx_interventions_mentor  on intervention_logs(mentor_id);

-- ── cohort_snapshots ─────────────────────────────────────────
-- Pre-aggregated weekly snapshot for fast chart queries

create table if not exists cohort_snapshots (
  id              uuid primary key default gen_random_uuid(),
  week            int  not null unique,
  avg_risk_score  numeric(5,2) not null default 0,
  red_count       int not null default 0,
  amber_count     int not null default 0,
  green_count     int not null default 0,
  snapshotted_at  timestamptz default now()
);

-- ── Row Level Security ────────────────────────────────────────
-- The FastAPI backend uses the service role key which BYPASSES RLS.
-- These policies are for safety if the anon key is ever used directly.

alter table students           enable row level security;
alter table attendance_records enable row level security;
alter table grade_records      enable row level security;
alter table engagement_records enable row level security;
alter table sentiment_records  enable row level security;
alter table surveys            enable row level security;
alter table alerts             enable row level security;
alter table intervention_logs  enable row level security;
alter table mentors            enable row level security;
alter table cohort_snapshots   enable row level security;

-- Service role bypasses all RLS — no policies needed for backend.
-- Add permissive policies here if you later add Supabase Auth for direct client access.
