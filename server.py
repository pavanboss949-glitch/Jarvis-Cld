"""
Jarvis — FastAPI backend
Run: python server.py
Requires: ANTHROPIC_API_KEY environment variable
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import os
import json
import anthropic

app = FastAPI(title="Jarvis API", version="1.0.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── STATIC FILES ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── ANTHROPIC CLIENT ─────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
MODEL = "claude-sonnet-5"

# ── DATABASE ─────────────────────────────────────────────────────────────────
DB = "jarvis.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                title     TEXT NOT NULL,
                desc      TEXT DEFAULT '',
                priority  TEXT DEFAULT 'medium',
                due_date  TEXT,
                category  TEXT DEFAULT '',
                completed INTEGER DEFAULT 0,
                created   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                text     TEXT NOT NULL,
                fire_at  TEXT NOT NULL,
                fired    INTEGER DEFAULT 0,
                created  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS schedule_blocks (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                time_slot TEXT NOT NULL,
                label     TEXT NOT NULL,
                date      TEXT NOT NULL
            );
        """)
        conn.commit()


init_db()


# ── PYDANTIC MODELS ───────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    desc: Optional[str] = ""
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None
    category: Optional[str] = ""


class TaskPatch(BaseModel):
    completed: Optional[bool] = None
    title: Optional[str] = None
    priority: Optional[str] = None
    desc: Optional[str] = None
    category: Optional[str] = None


class ReminderCreate(BaseModel):
    text: str
    fire_at: str  # ISO datetime string


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


class RecommendRequest(BaseModel):
    tasks: list
    schedule: list


# ── SERVE HTML ────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_landing():
    return FileResponse("index.html")


@app.get("/app")
async def serve_app():
    return FileResponse("app.html")


# ── TASKS ─────────────────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def get_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created DESC"
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/tasks", status_code=201)
async def create_task(task: TaskCreate):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, desc, priority, due_date, category) VALUES (?,?,?,?,?)",
            (task.title, task.desc, task.priority, task.due_date, task.category)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: int, patch: TaskPatch):
    fields, vals = [], []
    if patch.completed is not None:
        fields.append("completed = ?")
        vals.append(int(patch.completed))
    if patch.title is not None:
        fields.append("title = ?")
        vals.append(patch.title)
    if patch.priority is not None:
        fields.append("priority = ?")
        vals.append(patch.priority)
    if patch.desc is not None:
        fields.append("desc = ?")
        vals.append(patch.desc)
    if patch.category is not None:
        fields.append("category = ?")
        vals.append(patch.category)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    vals.append(task_id)
    with get_db() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return dict(row)


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    return {"ok": True}


# ── SCHEDULE ──────────────────────────────────────────────────────────────────

@app.get("/api/schedule")
async def get_schedule():
    from datetime import date
    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM schedule_blocks WHERE date = ? ORDER BY time_slot",
            (today,)
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/schedule/optimize")
async def optimize_schedule():
    """Ask Claude to generate a time-blocked daily schedule from open tasks."""
    if not client:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set")

    with get_db() as conn:
        tasks = [dict(r) for r in conn.execute(
            "SELECT title, priority, due_date FROM tasks WHERE completed = 0 ORDER BY priority"
        ).fetchall()]

    if not tasks:
        return {"blocks": [], "message": "No open tasks to schedule."}

    prompt = f"""You are Jarvis, a productivity AI. Given these open tasks:
{json.dumps(tasks, indent=2)}

Suggest a time-blocked daily schedule for today (8am-6pm) in 30-min or 1-hour blocks.
Respond ONLY with a valid JSON array, no markdown, no commentary:
[{{"time": "09:00", "label": "Deep work: Task title"}}, ...]"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        blocks = json.loads(raw)
    except Exception:
        blocks = []

    from datetime import date
    today = date.today().isoformat()
    with get_db() as conn:
        conn.execute("DELETE FROM schedule_blocks WHERE date = ?", (today,))
        for b in blocks:
            conn.execute(
                "INSERT INTO schedule_blocks (time_slot, label, date) VALUES (?,?,?)",
                (b.get("time", ""), b.get("label", ""), today)
            )
        conn.commit()
    return {"blocks": blocks}


# ── REMINDERS ─────────────────────────────────────────────────────────────────

@app.get("/api/reminders")
async def get_reminders():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders ORDER BY fire_at"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/reminders", status_code=201)
async def create_reminder(reminder: ReminderCreate):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (text, fire_at) VALUES (?,?)",
            (reminder.text, reminder.fire_at)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


@app.delete("/api/reminders/{reminder_id}")
async def delete_reminder(reminder_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
    return {"ok": True}


# ── CHAT (STREAMING SSE) ──────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Stream chat responses from Claude using Server-Sent Events."""
    if not client:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set")

    # Inject current task context into system prompt
    with get_db() as conn:
        open_tasks = [dict(r) for r in conn.execute(
            "SELECT title, priority, due_date, category FROM tasks WHERE completed = 0 ORDER BY priority LIMIT 20"
        ).fetchall()]
        completed_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed = 1"
        ).fetchone()[0]

    system_prompt = f"""You are Jarvis, a highly capable personal AI assistant and productivity manager — like Iron Man's Jarvis but for everyday productivity.

You have real-time access to the user's task list and help them manage their time, priorities, and workflow.

Current open tasks ({len(open_tasks)} total):
{json.dumps(open_tasks, indent=2) if open_tasks else "None yet."}

Completed tasks: {completed_count}

Be concise, direct, and actionable. Address the user as if you're their trusted AI chief-of-staff. Use markdown formatting for lists and emphasis when helpful. Offer proactive suggestions about task prioritization and time management."""

    messages = [{"role": m.role, "content": m.content} for m in req.history[-20:]]
    messages.append({"role": "user", "content": req.message})

    async def generate():
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    # Escape newlines for SSE
                    escaped = text.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── AUTO RECOMMENDATIONS ──────────────────────────────────────────────────────

@app.post("/api/recommendations")
async def get_recommendations(req: RecommendRequest):
    """One proactive suggestion from Jarvis based on tasks and schedule."""
    if not client:
        return {"suggestion": "Set your ANTHROPIC_API_KEY to enable AI recommendations. In the meantime — start by adding your most important task for today!"}

    prompt = f"""You are Jarvis, a productivity AI assistant. Give ONE short, specific, actionable suggestion (2-3 sentences max) based on the user's current state.

Tasks: {json.dumps(req.tasks[:10])}
Schedule blocks today: {len(req.schedule)}

Focus on the highest-priority incomplete items, scheduling gaps, or overdue work. Be direct and specific — no fluff."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    return {"suggestion": message.content[0].text}


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n🤖 Jarvis is starting up...")
    print("   Landing page → http://localhost:8000/")
    print("   App          → http://localhost:8000/app")
    print("   API docs     → http://localhost:8000/docs\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
