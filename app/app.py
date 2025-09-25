hereadmin_monitor_app.py

Minimal FastAPI app: admin-only сайт для мониторинга боттар

UI барлық мәтіндері - O'zbek (latin). Әңгіме қазақ тілінде беріледі.

import os import sqlite3 from typing import Optional from fastapi import FastAPI, Request, Form, Depends, HTTPException, status from fastapi.responses import HTMLResponse, RedirectResponse from fastapi.staticfiles import StaticFiles from starlette.middleware.sessions import SessionMiddleware from cryptography.fernet import Fernet from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "Bot Monitor - Admin" ADMIN_USER = os.getenv("ADMIN_USER", "admin") ADMIN_PASS = os.getenv("ADMIN_PASS", "changeme") SECRET_KEY = os.getenv("SECRET_KEY", "secret-session-key") FERNET_KEY = os.getenv("FERNET_KEY") if not FERNET_KEY: # fail early: FERNET_KEY required raise RuntimeError("FERNET_KEY muhim! generate qiling: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"") fernet = Fernet(FERNET_KEY.encode())

DB_PATH = os.getenv("DATABASE_PATH", "monitor.db")

app = FastAPI(title=APP_TITLE) app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

static dir if needed

if not os.path.exists("static"): os.makedirs("static") app.mount("/static", StaticFiles(directory="static"), name="static")

--- DB helpers ---

def get_db_conn(): conn = sqlite3.connect(DB_PATH) conn.row_factory = sqlite3.Row return conn

def init_db(): conn = get_db_conn() cur = conn.cursor() cur.execute(""" CREATE TABLE IF NOT EXISTS projects ( id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, github_repo TEXT, render_service_id TEXT, bot_token_enc TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP ) """) conn.commit() conn.close()

init_db()

--- Auth dependency ---

async def require_admin(request: Request): user = request.session.get("user") if not user: raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, detail="Redirect to login") if user.get("username") != ADMIN_USER: raise HTTPException(status_code=403, detail="Forbidden") return True

--- Templates (simple inline) ---

def render_html(content: str, title: str = ""): return HTMLResponse(f""" <html> <head> <meta charset="utf-8" /> <title>{title or APP_TITLE}</title> <style> body {{ font-family: Inter, Arial, sans-serif; padding:20px; max-width:1000px; margin:auto }} .card {{ border:1px solid #e5e7eb; padding:16px; border-radius:8px; margin-bottom:12px }} .top {{ display:flex; justify-content:space-between; align-items:center }} .leftnav {{ width:220px }} a.button {{ background:#111827; color:#fff; padding:8px 12px; border-radius:6px; text-decoration:none }} table {{ width:100%; border-collapse:collapse }} th, td {{ text-align:left; padding:8px; border-bottom:1px solid #f3f4f6 }} label {{ display:block; margin-top:8px }} </style> </head> <body> <div class="top"><h2>{APP_TITLE}</h2><div><a class="button" href="/logout">Chiqish</a></div></div> {content} </body> </html> """)

--- Routes ---

@app.get("/", response_class=HTMLResponse) async def index(request: Request): # redirect to dashboard or login if request.session.get("user"): return RedirectResponse(url="/dashboard") return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse) async def login_get(request: Request): html = """ <div class="card"> <h3>Login (Admin)</h3> <form method="post" action="/login"> <label>Foydalanuvchi nomi (username):<input name="username"/></label> <label>Parol (password):<input name="password" type="password"/></label> <button type="submit">Kirish</button> </form> </div> """ return render_html(html, title="Kirish")

@app.post("/login") async def login_post(request: Request, username: str = Form(...), password: str = Form(...)): # simple check — in production use hashed password and proper auth if username == ADMIN_USER and password == ADMIN_PASS: request.session["user"] = {"username": username} return RedirectResponse(url="/dashboard", status_code=303) else: html = """ <div class="card"> <h3>Kirish muvaffaqiyatsiz</h3> <p>Foydalanuvchi nomi yoki parol noto'g'ri.</p> <a href="/login">Qayta urinish</a> </div> """ return render_html(html, title="Kirish xato")

@app.get("/logout") async def logout(request: Request): request.session.pop("user", None) return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse) async def dashboard(request: Request, auth=Depends(require_admin)): conn = get_db_conn() cur = conn.cursor() cur.execute("SELECT id, name, github_repo, render_service_id, created_at FROM projects ORDER BY id DESC") rows = cur.fetchall() conn.close() items_html = "" for r in rows: items_html += f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['github_repo'] or '-'}</td><td>{r['render_service_id'] or '-'}</td><td>{r['created_at']}</td><td><a href='/project/{r['id']}'>Ochish</a></td></tr>" html = f""" <div class="card"> <h3>Projects</h3> <a href="/projects/new">+ Yangi project</a> <table> <thead><tr><th>ID</th><th>Nomi</th><th>GitHub</th><th>Render ID</th><th>Yaratildi</th><th></th></tr></thead> <tbody> {items_html} </tbody> </table> </div> """ return render_html(html, title="Dashboard")

@app.get("/projects/new", response_class=HTMLResponse) async def projects_new_get(request: Request, auth=Depends(require_admin)): html = """ <div class="card"> <h3>Yangi project qo'shish</h3> <form method="post" action="/projects/new"> <label>Project nomi: <input name="name" required/></label> <label>GitHub repo (owner/repo): <input name="github_repo"/></label> <label>Render service id: <input name="render_service_id"/></label> <label>Bot token (optional): <input name="bot_token"/></label> <button type="submit">Saqlash</button> </form> </div> """ return render_html(html, title="Yangi project")

@app.post("/projects/new") async def projects_new_post(request: Request, name: str = Form(...), github_repo: Optional[str] = Form(None), render_service_id: Optional[str] = Form(None), bot_token: Optional[str] = Form(None), auth=Depends(require_admin)): enc = None if bot_token: enc = fernet.encrypt(bot_token.encode()).decode() conn = get_db_conn() cur = conn.cursor() cur.execute("INSERT INTO projects (name, github_repo, render_service_id, bot_token_enc) VALUES (?,?,?,?)", (name, github_repo, render_service_id, enc)) conn.commit() conn.close() return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/project/{project_id}", response_class=HTMLResponse) async def project_view(request: Request, project_id: int, auth=Depends(require_admin)): conn = get_db_conn() cur = conn.cursor() cur.execute("SELECT * FROM projects WHERE id=?", (project_id,)) row = cur.fetchone() conn.close() if not row: return HTMLResponse("Project topilmadi", status_code=404) bot_token_display = '-' if row['bot_token_enc']: try: bot_token_display = '••••' + fernet.decrypt(row['bot_token_enc'].encode()).decode()[-6:] except Exception: bot_token_display = 'Encrypted' html = f""" <div class="card"> <h3>Project: {row['name']}</h3> <p><strong>GitHub:</strong> {row['github_repo'] or '-'}</p> <p><strong>Render service id:</strong> {row['render_service_id'] or '-'}</p> <p><strong>Bot token:</strong> {bot_token_display}</p> <a href='/project/{project_id}/logs'>Logs</a> | <a href='/project/{project_id}/code'>Code</a> | <a href='/project/{project_id}/settings'>Sozlamalar</a> </div> """ return render_html(html, title=f"Project: {row['name']}")

@app.get("/project/{project_id}/settings", response_class=HTMLResponse) async def project_settings(request: Request, project_id: int, auth=Depends(require_admin)): conn = get_db_conn() cur = conn.cursor() cur.execute("SELECT * FROM projects WHERE id=?", (project_id,)) row = cur.fetchone() conn.close() if not row: return HTMLResponse("Project topilmadi", status_code=404) html = f""" <div class="card"> <h3>Sozlamalar — {row['name']}</h3> <form method="post" action="/project/{project_id}/settings"> <label>Project nomi: <input name="name" value="{row['name']}" required/></label> <label>GitHub repo (owner/repo): <input name="github_repo" value="{row['github_repo'] or ''}"/></label> <label>Render service id: <input name="render_service_id" value="{row['render_service_id'] or ''}"/></label> <label>Yangi bot token (agar almashmoqchi bo'lsangiz): <input name="bot_token"/></label> <button type="submit">Saqlash</button> </form> </div> """ return render_html(html, title=f"Sozlamalar — {row['name']}")

@app.post("/project/{project_id}/settings") async def project_settings_post(request: Request, project_id: int, name: str = Form(...), github_repo: Optional[str] = Form(None), render_service_id: Optional[str] = Form(None), bot_token: Optional[str] = Form(None), auth=Depends(require_admin)): enc = None if bot_token: enc = fernet.encrypt(bot_token.encode()).decode() conn = get_db_conn() cur = conn.cursor() if enc: cur.execute("UPDATE projects SET name=?, github_repo=?, render_service_id=?, bot_token_enc=? WHERE id=?", (name, github_repo, render_service_id, enc, project_id)) else: cur.execute("UPDATE projects SET name=?, github_repo=?, render_service_id=? WHERE id=?", (name, github_repo, render_service_id, project_id)) conn.commit() conn.close() return RedirectResponse(url=f"/project/{project_id}", status_code=303)

Placeholder endpoints for logs/code (to be implemented further)

@app.get("/project/{project_id}/logs", response_class=HTMLResponse) async def project_logs(request: Request, project_id: int, auth=Depends(require_admin)): html = """ <div class="card"> <h3>Logs (bu joy hali to'ldirilmagan)</h3> <p>Keyingi qadam: Render / GitHub / botlardan loglarni yig'ib, bu yerda ko'rsatamiz.</p> </div> """ return render_html(html)

@app.get("/project/{project_id}/code", response_class=HTMLResponse) async def project_code(request: Request, project_id: int, auth=Depends(require_admin)): html = """ <div class="card"> <h3>Code viewer (hala ishlanmoqda)</h3> <p>Keyingi qadam: GitHub API orqali fayllarni olib, tahrirlash va annotation qilish.</p> </div> """ return render_html(html)

--- Run instructions in README-style (kept in file header comment)

To run locally:

1) pip install fastapi uvicorn python-dotenv cryptography

2) export ADMIN_USER=admin

export ADMIN_PASS=safepass123

export SECRET_KEY=some_session_secret

export FERNET_KEY=<generate_with_cryptography>

(optional) export DATABASE_PATH=monitor.db

3) uvicorn admin_monitor_app:app --host 0.0.0.0 --port 8000

Deploy on Render:

- Create a new web service, set start command to: uvicorn admin_monitor_app:app --host 0.0.0.0 --port $PORT

- Set environment variables in Render dashboard (ADMIN_USER, ADMIN_PASS, SECRET_KEY, FERNET_KEY)

- Add GitHub repo for this project and deploy

