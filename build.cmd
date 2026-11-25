@echo off
rem Build course-qa. Double-click this file.
setlocal
cd /d "%~dp0"

set "MVN=D:\tools\maven\bin\mvn.cmd"

echo ============================================================
echo  Build course-qa
echo ============================================================
echo.

if not exist "%MVN%" (
    echo [ERROR] Maven not found at:
    echo         %MVN%
    echo.
    pause
    exit /b 1
)

cmd /c "%MVN%" clean package -DskipTests
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
    echo [OK] Build succeeded. Now run start.cmd
) else (
    echo [ERROR] Build failed with exit code %RC%
    echo        Check the messages above.
)
echo.
pause
