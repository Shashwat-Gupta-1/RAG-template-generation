@echo off
echo Starting FastAPI Python Backend on http://localhost:8000 ...
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
pause
