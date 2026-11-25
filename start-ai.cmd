@echo off
rem Start course-qa with the DeepSeek key from .env
setlocal
cd /d "%~dp0"

set "JAVA=C:\Users\28443\jdk\jdk-25.0.4.1+1\bin\java.exe"
set "JAR=%~dp0target\course-qa-0.1.0.jar"

if not exist "%JAVA%" (
    echo [ERROR] Java not found: %JAVA%
    pause
    exit /b 1
)
if not exist "%JAR%" (
    echo [ERROR] Jar not found. Run build.cmd first.
    pause
    exit /b 1
)
if not exist "%~dp0.env" (
    echo [ERROR] .env not found in %~dp0
    pause
    exit /b 1
)

rem Load KEY=VALUE lines, skipping comments
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v /b "#" "%~dp0.env"`) do (
    if not "%%A"=="" set "%%A=%%B"
)

if "%LLM_API_KEY%"=="" (
    echo [WARN] LLM_API_KEY is empty, will fall back to mock mode? Check .env
)

echo ============================================================
echo  course-qa  (DeepSeek mode)
echo  retrieval : %QA_RETRIEVAL_MODE%
echo  llm mode  : %QA_LLM_MODE%
echo  model     : %LLM_MODEL%
echo  api key   : configured
echo ============================================================
echo.
echo  Wait for "Started QaApplication", then open:
echo    http://127.0.0.1:8080
echo.
echo  Keep this window open. Ctrl+C stops the service.
echo.

"%JAVA%" -jar "%JAR%"

echo.
echo Service stopped.
pause
