@REM @echo off
@REM cd /d "%~dp0"
@REM call myenv\Scripts\activate
@REM streamlit run main.py
@REM pause

@echo off
cd /d "%~dp0"
call myenv\Scripts\activate
start uvicorn backend:app --reload

