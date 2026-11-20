@echo off
rem  GTA 6 AutoClip - double-click, paste a YouTube link, get finished Shorts.
rem  First run installs what it needs (Python packages + ffmpeg). Your own videos only.
setlocal EnableExtensions
cd /d "%~dp0"
title GTA 6 AutoClip

where python >nul 2>nul || (
  echo Python is not installed. Installing it now...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo Python installed. Close this window and double-click AutoClip.bat again.
  pause & exit /b
)
where ffmpeg >nul 2>nul || (
  echo ffmpeg is not installed. Installing it now...
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  echo.
  echo ffmpeg installed. Close this window and double-click AutoClip.bat again.
  pause & exit /b
)
where deno >nul 2>nul || (
  echo Installing Deno, which YouTube downloads need...
  winget install -e --id DenoLand.Deno --accept-package-agreements --accept-source-agreements
  echo.
  echo Deno installed. Close this window and double-click AutoClip.bat again.
  pause & exit /b
)
if not exist ".autoclip_ready" (
  echo First run: installing the clip tools, this takes a few minutes...
  python -m pip install --upgrade -r creator\requirements.txt || (echo Install failed. & pause & exit /b)
  echo ok> .autoclip_ready
)
python -m pip install --upgrade --quiet yt-dlp >nul 2>nul

if exist ".autoclip_channel" (set /p CHANNEL=<.autoclip_channel) else (
  set /p CHANNEL=Your YouTube channel name:
)
if not exist ".autoclip_channel" (>.autoclip_channel echo %CHANNEL%)

echo.
set /p URL=Paste the YouTube link (or drag a video file here) and press Enter:
if "%URL%"=="" (echo No link given. & pause & exit /b)
set URL=%URL:"=%

set OUT=clips\run_%RANDOM%

echo.
echo Working... (download, speech-to-text, finding moments, cutting clips)
echo The first video takes longest because the speech model downloads once.
echo.
python creator\autoclip.py "%URL%" --facecam auto --lang hi --font "Nirmala UI" --channel "%CHANNEL%" --out "%OUT%"
if errorlevel 1 (
  echo.
  echo Something went wrong. Copy the error above and paste it to Claude.
  pause & exit /b
)
echo.
echo All done! Opening your clips...
start "" "%OUT%"
start "" notepad "%OUT%\upload_sheet.md"
pause
