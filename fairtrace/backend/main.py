"""
FairTrace - FastAPI Backend Server
Run this file to start the backend.
Command: uvicorn main:app --reload --port 8000

All API routes are defined here.
The frontend React app calls these routes.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import io
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our modules
from bias_engine import load_csv, run_full_analysis
from gemini_helper import get_gemini_explanation
from database import (
    init_db, seed_demo_data,
    create_incident, get_all_incidents, close_incident,
    save_snapshot, get_all_snapshots
)

# ─── APP SETUP ────────────────────────────────────────────────────
app = FastAPI(
    title="FairTrace API",
    description="AI Bias Monitoring & Incident Management System",
    version="1.0.0"
)

# Allow React frontend to call this backend
# (CORS = Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── STARTUP ─────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    """Run when server starts. Creates database and seeds demo data."""
    print("🚀 FairTrace backend starting...")
    init_db()
    seed_demo_data()
    print("✅ FairTrace backend ready at http://localhost:8000")
    print("📖 API docs at http://localhost:8000/docs")


# ─── HEALTH CHECK ────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "FairTrace API is running", "status": "healthy"}

@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── CSV COLUMN PREVIEW ──────────────────────────────────────────
@app.post("/preview")
async def preview_csv(file: UploadFile = File(...)):
    """
    Upload a CSV and get back its column names and unique values.
    Used by the frontend to populate the column selector dropdowns.
    """
    content = await file.read()
    df, error = load_csv(content)

    if error:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {error}")

    # Get unique values for each column (first 20 only)
    column_values = {}
    for col in df.columns:
        unique_vals = df[col].dropna().unique().tolist()
        column_values[col] = [str(v) for v in unique_vals[:20]]

    return {
        "columns": list(df.columns),
        "column_values": column_values,
        "row_count": len(df),
        "col_count": len(df.columns)
    }


# ─── MAIN ANALYSIS ENDPOINT ──────────────────────────────────────
@app.post("/analyze")
async def analyze_csv(
    file: UploadFile = File(...),
    protected_col: str = Form(...),
    outcome_col: str = Form(...),
    positive_val: str = Form(...),
    dataset_label: str = Form(default="Uploaded Dataset")
):
    """
    The core endpoint. Upload CSV + configuration → get full bias report.

    Steps:
    1. Parse CSV
    2. Run all bias algorithms (DIR, SPD, proxies, etc.)
    3. Call Gemini for plain-language explanation
    4. Save snapshot for drift tracking
    5. Return full result
    """
    # Step 1: Parse CSV
    content = await file.read()
    df, error = load_csv(content)

    if error:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {error}")

    # Validate columns exist
    if protected_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{protected_col}' not found in CSV")
    if outcome_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{outcome_col}' not found in CSV")

    # Check positive_val exists in outcome column
    actual_vals = df[outcome_col].dropna().unique().tolist()
    if positive_val not in [str(v) for v in actual_vals]:
        raise HTTPException(
            status_code=400,
            detail=f"Value '{positive_val}' not found in column '{outcome_col}'. Available: {actual_vals[:5]}"
        )

    # Convert outcome column to string for comparison
    df[outcome_col] = df[outcome_col].astype(str)

    # Step 2: Run bias algorithms
    analysis = run_full_analysis(df, protected_col, outcome_col, positive_val)

    # Step 3: Get Gemini explanation
    explanation = get_gemini_explanation(analysis)
    analysis["explanation"] = explanation

    # Step 4: Save snapshot for drift tracking
    save_snapshot({
        "label": dataset_label,
        "dir_value": analysis["dir"],
        "spd_value": analysis["spd"],
        "severity": analysis["severity"],
        "total": analysis["total"],
        "flagged": analysis["flagged"],
        "protected_col": protected_col,
        "outcome_col": outcome_col
    })

    # Step 5: Return everything
    analysis["dataset_label"] = dataset_label
    return analysis


# ─── INCIDENT ENDPOINTS ──────────────────────────────────────────

class IncidentCreate(BaseModel):
    severity: str
    title: str
    dataset_label: Optional[str] = None
    dir_value: Optional[float] = None
    spd_value: Optional[float] = None
    flagged: Optional[int] = None
    total: Optional[int] = None
    owner_name: Optional[str] = "Unassigned"
    owner_role: Optional[str] = ""
    escalate_to: Optional[str] = ""
    escalate_hours: Optional[int] = 24
    protected_col: Optional[str] = None
    outcome_col: Optional[str] = None
    positive_val: Optional[str] = None


@app.post("/incidents")
async def create_new_incident(incident: IncidentCreate):
    """Create a new bias incident record."""
    result = create_incident(incident.dict())
    return result


@app.get("/incidents")
async def list_incidents():
    """Get all incidents with their timeline events."""
    incidents = get_all_incidents()
    return {"incidents": incidents, "total": len(incidents)}


@app.put("/incidents/{incident_id}/close")
async def resolve_incident(incident_id: str):
    """Mark an incident as resolved and closed."""
    result = close_incident(incident_id)
    return result


# ─── SNAPSHOT / DRIFT ENDPOINTS ──────────────────────────────────

@app.get("/snapshots")
async def list_snapshots():
    """Get all drift snapshots for the drift chart."""
    snapshots = get_all_snapshots()
    return {"snapshots": snapshots, "total": len(snapshots)}


# ─── SAMPLE CSV DOWNLOAD ─────────────────────────────────────────
@app.get("/sample-csv")
async def get_sample_csv():
    """Return a sample CSV file for testing."""
    from fastapi.responses import Response
    csv_content = """ApplicantID,Gender,Age,YearsExperience,UniversityRank,EmploymentGap,Hired
1,Male,29,5,1,0,Yes
2,Female,27,4,2,1,No
3,Male,32,8,1,0,Yes
4,Female,28,5,1,0,No
5,Male,25,3,3,0,Yes
6,Female,30,6,1,1,No
7,Male,35,10,1,0,Yes
8,Female,26,3,2,0,Yes
9,Male,28,4,2,1,Yes
10,Female,33,7,1,0,No
11,Male,24,2,3,0,Yes
12,Female,29,5,2,1,No
13,Male,31,7,1,0,Yes
14,Female,27,4,3,0,No
15,Male,30,6,2,0,Yes
16,Female,28,5,1,1,No
17,Male,26,3,2,0,Yes
18,Female,32,8,1,0,Yes
19,Male,29,5,3,1,No
20,Female,25,2,3,0,No
21,Male,34,9,1,0,Yes
22,Female,28,4,2,1,No
23,Male,27,3,2,0,Yes
24,Female,30,6,1,0,No
25,Male,33,8,1,1,Yes
26,Female,26,3,3,0,No
27,Male,29,5,2,0,Yes
28,Female,31,7,1,0,No
29,Male,28,4,2,0,Yes
30,Female,27,3,2,1,No
31,Male,35,10,1,0,Yes
32,Female,29,5,1,0,No
33,Male,26,3,3,0,Yes
34,Female,32,7,1,1,No
35,Male,30,6,2,0,Yes
36,Female,28,4,2,0,No
37,Male,27,4,3,0,Yes
38,Female,33,8,1,0,Yes
39,Male,31,7,2,1,No
40,Female,26,3,3,0,No
41,Male,29,5,1,0,Yes
42,Female,28,5,2,1,No
43,Male,24,2,3,0,Yes
44,Female,30,6,1,0,No
45,Male,32,8,1,0,Yes
46,Female,27,4,3,1,No
47,Male,35,10,1,0,Yes
48,Female,29,5,2,0,No
49,Male,28,4,1,0,Yes
50,Female,31,7,2,1,No
51,Male,26,3,3,0,Yes
52,Female,33,8,1,0,No
53,Male,30,6,2,0,Yes
54,Female,28,5,2,0,No
55,Male,27,3,3,0,Yes
56,Female,32,7,1,1,No
57,Male,34,9,1,0,Yes
58,Female,26,3,2,0,No
59,Male,29,5,1,0,Yes
60,Female,30,6,2,1,No"""

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_hiring_data.csv"}
    )