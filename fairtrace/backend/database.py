"""
FairTrace - Database
Uses SQLite (a simple file-based database, no server needed).
Stores: incidents, incident timelines, and drift snapshots.
The file fairtrace.db is created automatically in the backend folder.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "fairtrace.db")


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Makes rows behave like dicts
    return conn


def init_db():
    """
    Create all tables if they don't exist yet.
    Run once on startup.
    """
    conn = get_connection()
    c = conn.cursor()

    # Incidents table - one row per bias incident
    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            dataset_label TEXT,
            dir_value REAL,
            spd_value REAL,
            flagged INTEGER,
            total INTEGER,
            owner_name TEXT,
            owner_role TEXT,
            escalate_to TEXT,
            escalate_hours INTEGER DEFAULT 24,
            status TEXT DEFAULT 'open',
            protected_col TEXT,
            outcome_col TEXT,
            positive_val TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Incident timeline table - audit trail of actions per incident
    c.execute("""
        CREATE TABLE IF NOT EXISTS incident_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            time_label TEXT,
            message TEXT,
            event_type TEXT,
            created_at TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        )
    """)

    # Snapshots table - each CSV upload is a drift snapshot
    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            dir_value REAL,
            spd_value REAL,
            severity TEXT,
            total INTEGER,
            flagged INTEGER,
            protected_col TEXT,
            outcome_col TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized at:", DB_PATH)


def seed_demo_data():
    """
    Add sample data so the dashboard looks populated from first run.
    Only runs if no data exists.
    """
    conn = get_connection()
    c = conn.cursor()

    # Check if already seeded
    existing = c.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    now = datetime.now().isoformat()

    # Seed 6 drift snapshots showing worsening bias
    snapshots = [
        ("November 2024", 0.88, 0.09, "clear", 1200, 5, "Gender", "Hired"),
        ("December 2024", 0.83, 0.13, "clear", 980, 12, "Gender", "Hired"),
        ("January 2025", 0.79, 0.17, "medium", 1100, 28, "Gender", "Hired"),
        ("February 2025", 0.71, 0.22, "medium", 1340, 51, "Gender", "Hired"),
        ("March 2025", 0.64, 0.29, "critical", 1560, 98, "Gender", "Hired"),
        ("April 2025", 0.58, 0.34, "critical", 1840, 142, "Gender", "Hired"),
    ]
    for s in snapshots:
        c.execute("""
            INSERT INTO snapshots (label, dir_value, spd_value, severity, total, flagged, protected_col, outcome_col, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*s, now))

    # Seed incident 1 - Critical, escalated
    c.execute("""
        INSERT INTO incidents (id, severity, title, dataset_label, dir_value, spd_value, flagged, total,
            owner_name, owner_role, escalate_to, escalate_hours, status, protected_col, outcome_col,
            positive_val, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("INC-001", "critical", "Gender Bias — Loan Approval Model",
          "Q1 2025 Loan Applications", 0.58, 0.34, 142, 1840,
          "Sarah Chen", "Compliance Officer", "Legal Team", 24, "escalated",
          "Gender", "Approved", "Yes", now, now))

    timeline_1 = [
        ("INC-001", "12 days ago", "Critical bias detected — DIR 0.58 (legal min: 0.80)", "alert"),
        ("INC-001", "11 days ago", "Acknowledged by Sarah Chen (Compliance Officer)", "ack"),
        ("INC-001", "8 days ago", "Fix submitted by ML Engineering team", "action"),
        ("INC-001", "8 days ago", "Post-fix re-audit run — bias persists at DIR 0.61", "alert"),
        ("INC-001", "Today", "Auto-escalated to Legal Team — 12 days unresolved", "escalate"),
    ]
    for t in timeline_1:
        c.execute("""
            INSERT INTO incident_timeline (incident_id, time_label, message, event_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (*t, now))

    # Seed incident 2 - Medium, in review
    c.execute("""
        INSERT INTO incidents (id, severity, title, dataset_label, dir_value, spd_value, flagged, total,
            owner_name, owner_role, escalate_to, escalate_hours, status, protected_col, outcome_col,
            positive_val, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("INC-002", "medium", "Age Proxy Detected — Hiring Screening",
          "March Recruitment Batch", 0.74, 0.22, 38, 420,
          "Marcus Webb", "HR Director", "Compliance Team", 48, "in_review",
          "Age", "Hired", "Yes", now, now))

    timeline_2 = [
        ("INC-002", "4 days ago", "Medium bias detected — DIR 0.74", "alert"),
        ("INC-002", "3 days ago", "Acknowledged by Marcus Webb (HR Director)", "ack"),
        ("INC-002", "1 day ago", "Screening criteria audit initiated", "action"),
    ]
    for t in timeline_2:
        c.execute("""
            INSERT INTO incident_timeline (incident_id, time_label, message, event_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (*t, now))

    conn.commit()
    conn.close()
    print("✅ Demo data seeded successfully")


# ─── INCIDENT FUNCTIONS ───────────────────────────────────────────

def create_incident(data: dict) -> dict:
    """Create a new bias incident record."""
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()

    # Generate incident ID
    count = c.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    incident_id = f"INC-{str(count + 1).zfill(3)}"

    c.execute("""
        INSERT INTO incidents (id, severity, title, dataset_label, dir_value, spd_value, flagged, total,
            owner_name, owner_role, escalate_to, escalate_hours, status, protected_col, outcome_col,
            positive_val, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
    """, (
        incident_id,
        data.get("severity"),
        data.get("title"),
        data.get("dataset_label"),
        data.get("dir_value"),
        data.get("spd_value"),
        data.get("flagged"),
        data.get("total"),
        data.get("owner_name"),
        data.get("owner_role"),
        data.get("escalate_to"),
        data.get("escalate_hours", 24),
        data.get("protected_col"),
        data.get("outcome_col"),
        data.get("positive_val"),
        now, now
    ))

    # Add first timeline entry
    c.execute("""
        INSERT INTO incident_timeline (incident_id, time_label, message, event_type, created_at)
        VALUES (?, 'Just now', ?, 'alert', ?)
    """, (incident_id, f"Bias incident opened — DIR {data.get('dir_value')} detected", now))

    conn.commit()
    conn.close()
    return {"id": incident_id, "status": "created"}


def get_all_incidents() -> list:
    """Get all incidents with their timeline events."""
    conn = get_connection()
    c = conn.cursor()

    incidents = c.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
    result = []

    for inc in incidents:
        inc_dict = dict(inc)
        timeline = c.execute(
            "SELECT * FROM incident_timeline WHERE incident_id = ? ORDER BY id ASC",
            (inc_dict["id"],)
        ).fetchall()
        inc_dict["timeline"] = [dict(t) for t in timeline]
        result.append(inc_dict)

    conn.close()
    return result


def close_incident(incident_id: str) -> dict:
    """Mark an incident as resolved and closed."""
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()

    c.execute("""
        UPDATE incidents SET status = 'closed', updated_at = ? WHERE id = ?
    """, (now, incident_id))

    c.execute("""
        INSERT INTO incident_timeline (incident_id, time_label, message, event_type, created_at)
        VALUES (?, 'Just now', 'Incident marked as resolved and closed.', 'resolved', ?)
    """, (incident_id, now))

    conn.commit()
    conn.close()
    return {"id": incident_id, "status": "closed"}


# ─── SNAPSHOT FUNCTIONS ──────────────────────────────────────────

def save_snapshot(data: dict) -> dict:
    """Save a new drift snapshot after each CSV upload."""
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()

    c.execute("""
        INSERT INTO snapshots (label, dir_value, spd_value, severity, total, flagged, protected_col, outcome_col, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("label", "Snapshot"),
        data.get("dir_value"),
        data.get("spd_value"),
        data.get("severity"),
        data.get("total"),
        data.get("flagged"),
        data.get("protected_col"),
        data.get("outcome_col"),
        now
    ))

    conn.commit()
    conn.close()
    return {"status": "saved"}


def get_all_snapshots() -> list:
    """Get all snapshots for the drift chart."""
    conn = get_connection()
    c = conn.cursor()
    snapshots = c.execute("SELECT * FROM snapshots ORDER BY created_at ASC").fetchall()
    conn.close()
    return [dict(s) for s in snapshots]