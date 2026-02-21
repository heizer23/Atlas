from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_connection
from app.models import WorkoutLogCreate
import uuid
from datetime import date
from typing import Optional, List
import os
from pathlib import Path
import logging


from platform_errorhandling.logging import setup_logging
from platform_errorhandling.logFastapi import install_exception_handlers

# App and Templates
app = FastAPI(title="WorkoutTracker")

setup_logging(
    app_name="workouttracker",
    log_dir=Path(__file__).resolve().parents[1] / "logs",
)

log = logging.getLogger("workouttracker")
install_exception_handlers(app)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Determine paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
search_path = os.path.join(BASE_DIR, "templates")

# Debug print to verify path
log.info("Template path: %s", search_path)

templates = Jinja2Templates(directory=search_path)
templates.env.add_extension('jinja2.ext.do')

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/workouts")

@app.get("/workouts", response_class=HTMLResponse)
async def list_workouts(request: Request):
    """
    List workouts. 
    Since we have a single table, we group by workout_id to show 'Sessions'.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Group by workout_id, date, split. Get first exercise as preview?
            # Or just SELECT DISTINCT ON (workout_id) ...
            cur.execute("""
                SELECT DISTINCT ON (workout_id) 
                    workout_id, workout_date, split, created_at
                FROM workout.workout_log
                ORDER BY workout_id, workout_date DESC
            """)
            sessions = cur.fetchall()
            
            # Sort sessions by date desc properly (Python side or adjusting SQL)
            # DISTINCT ON needs the ORDER BY to match. 
            # Better query: Get sessions and counts
            cur.execute("""
                SELECT 
                    workout_id, 
                    MAX(workout_date) as workout_date, 
                    MAX(split) as split, 
                    COUNT(*) as exercise_count
                FROM workout.workout_log
                GROUP BY workout_id
                ORDER BY workout_date DESC
            """)
            sessions = cur.fetchall()

    return templates.TemplateResponse("list.html", {
        "request": request, 
        "sessions": sessions
    })

@app.get("/api/workouts")
async def api_list_workouts():
    """
    JSON endpoint for all workout sessions.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    workout_id, 
                    MAX(workout_date) as workout_date, 
                    MAX(split) as split, 
                    COUNT(*) as exercise_count
                FROM workout.workout_log
                GROUP BY workout_id
                ORDER BY workout_date DESC
            """)
            sessions = cur.fetchall()
            
            # Convert date objects to strings for JSON
            for s in sessions:
                if s['workout_date']:
                    s['workout_date'] = s['workout_date'].isoformat()
                s['workout_id'] = str(s['workout_id'])
                
    return sessions

@app.get("/api/workouts/{id}/exercises")
async def api_list_exercises(id: str):
    """
    JSON endpoint for all exercises in a specific workout session.
    """
    try:
        w_id = uuid.UUID(id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        workout_log_id,
                        exercise,
                        weight_kg,
                        set1_reps,
                        set2_reps,
                        set3_reps,
                        set4_reps,
                        set5_reps,
                        comment,
                        created_at
                    FROM workout.workout_log
                    WHERE workout_id = %s
                    ORDER BY created_at ASC
                """, (w_id,))
                exercises = cur.fetchall()
                
                # Convert to JSON-friendly format
                for ex in exercises:
                    ex['workout_log_id'] = int(ex['workout_log_id'])
                    if ex['created_at']:
                        ex['created_at'] = ex['created_at'].isoformat()
                    # Convert None to empty string for display
                    for key in ['comment', 'weight_kg', 'set1_reps', 'set2_reps', 'set3_reps', 'set4_reps', 'set5_reps']:
                        if ex[key] is None:
                            ex[key] = ''
                
        return exercises
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workout ID")

@app.get("/workouts/new", response_class=HTMLResponse)
async def new_workout_form(request: Request):
    today = date.today()
    new_uuid = uuid.uuid4()
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get last session for each split as "templates"
            cur.execute("""
                SELECT DISTINCT ON (split)
                    workout_id, workout_date, split, COUNT(*) over (partition by workout_id) as exercise_count
                FROM workout.workout_log
                ORDER BY split, workout_date DESC
            """)
            recent_templates = cur.fetchall()
            
    return templates.TemplateResponse("new.html", {
        "request": request, 
        "today": today,
        "new_uuid": new_uuid,
        "templates": recent_templates
    })

@app.post("/workouts")
async def create_workout(
    workout_date: str = Form(...),
    split: str = Form(...),
    workout_id: str = Form(...),
    # Dynamic form handling for multiple exercises is hard with pure Form arguments 
    # and no JS. For MVP, we stick to "One Exercise per Submit" OR 
    # we allow creating a "Session" first then adding exercises?
    # User requirement: "GET /workouts/new -> form for a new workout + sets"
    # "POST /workouts -> insert workout + sets transactionally"
    # This implies the FORM contains at least one exercise.
    # Let's support ONE exercise in the Main Form for now to be simple.
    exercise: str = Form(...),
    weight_kg: Optional[float] = Form(None),
    set1_reps: Optional[int] = Form(None),
    set2_reps: Optional[int] = Form(None),
    set3_reps: Optional[int] = Form(None),
    set4_reps: Optional[int] = Form(None),
    set5_reps: Optional[int] = Form(None),
    comment: Optional[str] = Form(None)
):
    try:
        w_id = uuid.UUID(workout_id)
        # Construct model to validate
        log = WorkoutLogCreate(
            workout_date=date.fromisoformat(workout_date),
            split=split,
            exercise=exercise,
            weight_kg=weight_kg,
            set1_reps=set1_reps,
            set2_reps=set2_reps,
            set3_reps=set3_reps,
            set4_reps=set4_reps,
            set5_reps=set5_reps,
            comment=comment,
            workout_id=w_id
        )

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO workout.workout_log (
                        workout_id, workout_date, split, exercise, weight_kg, 
                        set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    log.workout_id, log.workout_date, log.split, log.exercise, log.weight_kg,
                    log.set1_reps, log.set2_reps, log.set3_reps, log.set4_reps, log.set5_reps, log.comment
                ))
            conn.commit()
            
        return RedirectResponse(url=f"/workouts/{w_id}", status_code=303)

    except ValueError as e:
         return HTMLResponse(content=f"Error: {e}", status_code=400)

@app.get("/workouts/{id}", response_class=HTMLResponse)
async def detail_workout(request: Request, id: str, copy_id: Optional[int] = None, edit_id: Optional[int] = None):
    try:
        w_id = uuid.UUID(id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM workout.workout_log 
                    WHERE workout_id = %s
                    ORDER BY created_at ASC
                """, (w_id,))
                logs = cur.fetchall()
                
                prefill = None
                if copy_id:
                    cur.execute("SELECT * FROM workout.workout_log WHERE workout_log_id = %s", (copy_id,))
                    prefill = cur.fetchone()
        
        if not logs and not copy_id:
            return HTMLResponse("Workout not found", status_code=404)
        
        # Meta info from first row if exists, else we might still be in a 'newly' created empty session
        if logs:
            meta = {
                "workout_date": logs[0]["workout_date"],
                "split": logs[0]["split"],
                "workout_id": logs[0]["workout_id"]
            }
        else:
            # Fallback if session is empty (shouldn't happen with current logic but for safety)
             meta = {"workout_date": date.today(), "split": "N/A", "workout_id": w_id}

        return templates.TemplateResponse("detail.html", {
            "request": request, 
            "logs": logs, 
            "meta": meta,
            "prefill": prefill,
            "edit_id": edit_id
        })
    except ValueError:
        return HTMLResponse("Invalid UUID", status_code=400)

@app.post("/log/{log_id}/update")
async def update_workout_log(
    log_id: int,
    exercise: str = Form(...),
    weight_kg: Optional[float] = Form(None),
    set1_reps: Optional[int] = Form(None),
    set2_reps: Optional[int] = Form(None),
    set3_reps: Optional[int] = Form(None),
    set4_reps: Optional[int] = Form(None),
    set5_reps: Optional[int] = Form(None),
    comment: Optional[str] = Form(None)
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get workout_id first to redirect
            cur.execute("SELECT workout_id FROM workout.workout_log WHERE workout_log_id = %s", (log_id,))
            row = cur.fetchone()
            if not row:
                return HTMLResponse("Log not found", status_code=404)
            w_id = row['workout_id']

            cur.execute("""
                UPDATE workout.workout_log SET
                    exercise = %s, weight_kg = %s,
                    set1_reps = %s, set2_reps = %s, set3_reps = %s, set4_reps = %s, set5_reps = %s,
                    comment = %s, updated_at = NOW()
                WHERE workout_log_id = %s
            """, (exercise, weight_kg, set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment, log_id))
        conn.commit()
    return RedirectResponse(url=f"/workouts/{w_id}", status_code=303)

@app.post("/log/{log_id}/delete")
async def delete_workout_log(log_id: int):
    log.debug("Deleting workout log %s", log_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get workout_id first to redirect
            cur.execute("SELECT workout_id FROM workout.workout_log WHERE workout_log_id = %s", (log_id,))
            row = cur.fetchone()
            if not row:
                log.debug("Log ID %s not found", log_id)
                return HTMLResponse("Log not found", status_code=404)
            w_id = row['workout_id']
            
            # Delete
            cur.execute("DELETE FROM workout.workout_log WHERE workout_log_id = %s", (log_id,))
            log.debug("Delete affected %s rows", cur.rowcount)

            # Check if session still has exercises
            cur.execute("SELECT COUNT(*) FROM workout.workout_log WHERE workout_id = %s", (w_id,))
            count = cur.fetchone()['count']
            
        conn.commit()
            
    # If session is now empty, go back to list, else stay in detail
    if count == 0:
        return RedirectResponse(url="/workouts", status_code=303)
    return RedirectResponse(url=f"/workouts/{w_id}", status_code=303)

@app.post("/workouts/{id}/update_meta")
async def update_workout_meta(
    id: str,
    workout_date: str = Form(...),
    split: str = Form(...)
):
    try:
        w_id = uuid.UUID(id)
        new_date = date.fromisoformat(workout_date)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE workout.workout_log SET
                        workout_date = %s,
                        split = %s,
                        updated_at = NOW()
                    WHERE workout_id = %s
                """, (new_date, split, w_id))
            conn.commit()
        return RedirectResponse(url=f"/workouts/{w_id}", status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"Error updating session: {e}", status_code=400)

@app.post("/workouts/{id}/delete")
async def delete_workout_session(id: str):
    log.debug("Deleting workout session %s", id)
    try:
        w_id = uuid.UUID(id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workout.workout_log WHERE workout_id = %s", (w_id,))
                conn.commit()
        return RedirectResponse(url="/workouts", status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"Error deleting session: {e}", status_code=400)

@app.post("/workouts/{id}/copy_session")
async def copy_workout_session(id: str):
    try:
        w_id = uuid.UUID(id)
        new_w_id = uuid.uuid4()
        today = date.today()
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get the split name from the original session
                cur.execute("SELECT split FROM workout.workout_log WHERE workout_id = %s LIMIT 1", (w_id,))
                row = cur.fetchone()
                if not row:
                    return HTMLResponse("Session not found", status_code=404)
                split = row['split']
                
                # Fetch all exercises from original session
                cur.execute("""
                    SELECT exercise, weight_kg, pause_sec, set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
                    FROM workout.workout_log
                    WHERE workout_id = %s
                    ORDER BY created_at ASC
                """, (w_id,))
                exercises = cur.fetchall()
                
                if not exercises:
                    return HTMLResponse("No exercises found in session", status_code=404)
                
                # Insert them into the new session
                for ex in exercises:
                    cur.execute("""
                        INSERT INTO workout.workout_log (
                            workout_id, workout_date, split, exercise, weight_kg, pause_sec,
                            set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        new_w_id, today, split, ex['exercise'], ex['weight_kg'], ex['pause_sec'],
                        ex['set1_reps'], ex['set2_reps'], ex['set3_reps'], ex['set4_reps'], ex['set5_reps'], ex['comment']
                    ))
            conn.commit()
            
        return RedirectResponse(url=f"/workouts/{new_w_id}", status_code=303)
    except ValueError:
        return HTMLResponse("Invalid UUID", status_code=400)

@app.post("/workouts/{id}/add")
async def add_exercise_to_workout(
    id: str,
    exercise: str = Form(...),
    weight_kg: Optional[float] = Form(None),
    set1_reps: Optional[int] = Form(None),
    set2_reps: Optional[int] = Form(None),
    set3_reps: Optional[int] = Form(None),
    set4_reps: Optional[int] = Form(None),
    set5_reps: Optional[int] = Form(None),
    comment: Optional[str] = Form(None)
):
    # Fetch date/split from existing session to ensure consistency?
    # Or just require them in Hidden Form Fields?
    # We'll fetch them for safety.
    w_id = uuid.UUID(id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT workout_date, split FROM workout.workout_log WHERE workout_id = %s LIMIT 1", (w_id,))
            row = cur.fetchone()
            if not row:
                return HTMLResponse("Session not found", status_code=404)
            
            workout_date = row['workout_date']
            split = row['split']

            cur.execute("""
                INSERT INTO workout.workout_log (
                    workout_id, workout_date, split, exercise, weight_kg, 
                    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                w_id, workout_date, split, exercise, weight_kg,
                set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
            ))
        conn.commit()
    
    return RedirectResponse(url=f"/workouts/{w_id}", status_code=303)
