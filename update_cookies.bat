@echo off
REM YouTube 쿠키 자동 갱신 스크립트
REM Windows 작업 스케줄러에 등록하여 주기적으로 실행

cd /d "%~dp0"

echo [%date% %time%] 쿠키 갱신 시작... >> cookie_update.log

REM Firefox 쿠키 추출 (Firefox가 설치되어 있어야 함)
yt-dlp --cookies-from-browser firefox --cookies cookies.txt --skip-download "https://www.youtube.com" 2>> cookie_update.log

if %errorlevel% == 0 (
    echo [%date% %time%] 쿠키 갱신 성공 >> cookie_update.log

    REM Docker 컨테이너 재시작 (선택사항)
    REM docker compose restart yt-monitor yt-web
) else (
    echo [%date% %time%] 쿠키 갱신 실패 >> cookie_update.log
)
