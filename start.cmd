@echo off
rem Start course-qa. Double-click this file. No PATH or working-directory requirement.
setlocal
cd /d "%~dp0"

set "JAVA=C:\Users\28443\jdk\jdk-25.0.4.1+1\bin\java.exe"
set "JAR=%~dp0target\course-qa-0.1.0.jar"

echo ============================================================
echo  course-qa  :  B1 RAG course knowledge base QA
echo ============================================================
echo.

if not exist "%JAVA%" (
    echo [ERROR] Java not found at:
    echo         %JAVA%
    echo.
    pause
    exit /b 1
)

if not exist "%JAR%" (
    echo [ERROR] Jar not found:
    echo         %JAR%
    echo.
    echo         Run build.cmd first to build the project.
    echo.
    pause
    exit /b 1
)

echo Starting on http://127.0.0.1:8080
echo.
echo  1. Wait for the line:  "Started QaApplication"
echo  2. Then open http://127.0.0.1:8080 in your browser
echo  3. Keep this window open. Press Ctrl+C to stop the service.
echo.

"%JAVA%" -jar "%JAR%"

echo.
echo Service stopped.
pause
