@echo off
cd /d "%~dp0backend"
title Chi tieu cua toi - Expense AI

python --version >nul 2>nul || (
  echo [!] Chua cai Python. Tai Python 3.10 tro len tai python.org va tick "Add python.exe to PATH" khi cai.
  pause
  exit /b 1
)

if not exist .env (
  copy .env.example .env >nul
  echo Hay dan GEMINI_API_KEY vao file .env, luu lai roi dong Notepad. Lay key mien phi tai aistudio.google.com/apikey
  notepad .env
)

if not exist .venv\Scripts\python.exe (
  echo Dang tao moi truong ao, chi can lam lan dau...
  python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo Dang cai thu vien, lan dau co the mat vai phut va can co mang...
pip install -q -r requirements.txt || (pause & exit /b 1)

if not exist ..\model\category_model.joblib (
  echo Dang huan luyen model phan loai danh muc...
  pushd ..\model
  python train_export.py
  popd
)

echo Dang mo http://127.0.0.1:8000 ... Dong cua so nay de tat app.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"
python -m uvicorn app.main:app --port 8000
pause
