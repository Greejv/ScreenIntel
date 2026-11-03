@echo off
REM Builds dist\ScreenIntel.exe. Run from this folder in PowerShell or cmd.
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --onefile --noconsole --name ScreenIntel main.py || exit /b 1
if exist .env (copy /Y .env dist\.env >nul) else (echo WARNING: no .env here, put GEMINI_API_KEY=... in dist\.env)
echo.
echo Done: dist\ScreenIntel.exe  (keeps its API key in dist\.env)
