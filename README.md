# Jarvis — Operational AI Infrastructure

> Your personal AI productivity manager powered by Claude — manage tasks, optimise your schedule, run Pomodoro sessions, set reminders, and chat with an AI assistant that knows your workload.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)
![Claude](https://img.shields.io/badge/Claude-Sonnet--5-blueviolet?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

---

## Features

| Feature | Description |
|---------|-------------|
| **Task Manager** | Add tasks with priority (High/Medium/Low), due dates, categories — stored in SQLite |
| **AI Schedule Optimizer** | Claude generates a time-blocked daily schedule from your open tasks |
| **Pomodoro Timer** | 25/5 min focus/break cycle with progress bar and notifications |
| **AI Chat** | Streaming Claude chat — context-aware of your tasks (`Ctrl+K` anywhere) |
| **Reminders** | Browser push notifications at a date/time you choose |
| **Auto Recommendations** | Jarvis proactively suggests what to focus on when you open the app |

---

## Quick Start

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com)

### 1. Clone

```bash
git clone https://github.com/your-username/jarvis.git
cd jarvis
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
# Copy the example and add your key
cp .env.example .env
```

Edit `.env`:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Then load it before running:

```bash
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = (Get-Content .env | Select-String "ANTHROPIC_API_KEY").ToString().Split("=")[1]

# macOS / Linux
export $(cat .env | xargs)
```

### 4. Run

```bash
python server.py
```

| URL | Page |
|-----|------|
| http://localhost:8000/ | Landing page |
| http://localhost:8000/app | Jarvis app |
| http://localhost:8000/docs | Interactive API docs |

---

## Project Structure

```
jarvis/
├── index.html          # Landing page (self-contained — inline CSS + JS)
├── app.html            # App UI shell
├── server.py           # FastAPI backend
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .gitignore
├── static/
│   ├── app.css         # App styles (dark theme)
│   └── app.js          # Frontend logic (SPA)
└── README.md
```

> `jarvis.db` is created automatically on first run and is excluded from version control.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tasks` | List all tasks |
| `POST` | `/api/tasks` | Create a task |
| `PATCH` | `/api/tasks/{id}` | Update a task |
| `DELETE` | `/api/tasks/{id}` | Delete a task |
| `GET` | `/api/schedule` | Today's schedule blocks |
| `POST` | `/api/schedule/optimize` | AI-generate a schedule |
| `GET` | `/api/reminders` | List reminders |
| `POST` | `/api/reminders` | Create a reminder |
| `DELETE` | `/api/reminders/{id}` | Delete a reminder |
| `POST` | `/api/chat` | Streaming chat (SSE) |
| `POST` | `/api/recommendations` | Proactive AI suggestion |

Full interactive docs at `/docs` when the server is running.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` / `Cmd+K` | Open chat from anywhere |
| `Escape` | Close modal / sidebar |
| `Enter` in task title | Save task |
| `Enter` in chat | Send message |
| `Shift+Enter` in chat | New line |

---

## Stack

- **Backend** — [FastAPI](https://fastapi.tiangolo.com) + [Uvicorn](https://www.uvicorn.org), SQLite via stdlib `sqlite3`
- **AI** — [Anthropic Python SDK](https://github.com/anthropic-ai/anthropic-sdk-python), model `claude-sonnet-5`
- **Frontend** — Vanilla JS (no framework), Inter + Instrument Serif fonts
- **Landing page** — Single HTML file with inline CSS and a small IIFE

---

## License

MIT — see [LICENSE](LICENSE) for details.
