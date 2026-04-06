@echo off
echo === YouTube Cookie Refresh ===
echo Extracting cookies from Firefox...
echo.

cd /d "%~dp0"
uv run yt-dlp --cookies-from-browser firefox --cookies cookies.txt --skip-download "https://www.youtube.com/watch?v=jNQXAC9IVRw"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] cookies.txt updated successfully.
    echo Docker container will pick it up via volume mount.
) else (
    echo.
    echo [FAIL] Cookie extraction failed.
    echo Make sure Firefox is fully closed and try again.
)

echo.
pause
