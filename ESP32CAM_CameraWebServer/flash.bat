@echo off
setlocal
title AR Glass - ESP32-CAM Flash

rem ================================================================
rem  ESP32-CAM flash (CameraWebServer firmware)
rem  Compiles with arduino-cli, then uploads the FULL image
rem  (merged.bin at 0x0) with esptool at 115200 baud.
rem  115200 baud is used because 460800 fails with
rem  "Unable to verify flash chip connection" on these boards.
rem ================================================================

set "CLI=C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"
set "FQBN=esp32:esp32:esp32cam"
set "SKETCH=%~dp0CameraWebServer"
set "BUILD=%~dp0build"
set "ESPOOL=C:\Users\user\AppData\Local\Arduino15\packages\esp32\tools"

if not exist "%CLI%" (
  echo [ERROR] arduino-cli not found: %CLI%
  echo         Install Arduino IDE 2.x at the default location.
  goto :end
)

echo ============================================================
echo   ESP32-CAM Flash  (CameraWebServer firmware)
echo ============================================================
echo.
echo  1) Connect ONE board to the USB-TTL (CH340) programmer.
echo     - Carrier boards with auto-reset: just plug in.
echo     - Bare boards: hold IO0, tap RST, release IO0.
echo  2) Run this script, pick the COM port.
echo  3) After flashing LEFT, switch AR_GLASS_BOARD to 1 in
echo     CameraWebServer\wifi_config.h and reflash for RIGHT.
echo.

"%CLI%" board list
echo.
set "COM="
set /p "COM=Enter COM port to flash (e.g. COM25): "
if "%COM%"=="" goto :end

echo.
echo  Compiling ...
"%CLI%" compile --fqbn %FQBN% --output-dir "%BUILD%" "%SKETCH%"
if errorlevel 1 goto :fail

set "ESPT=notfound"
if exist "%ESPOOL%\esptool_py\5.3.1\esptool.exe" set "ESPT=%ESPOOL%\esptool_py\5.3.1\esptool.exe"
if "%ESPT%"=="notfound" (
  for /f "delims=" %%i in ('dir /b /s "%ESPOOL%\esptool_py\esptool.exe" 2^>nul') do set "ESPT=%%i"
)
if "%ESPT%"=="notfound" (
  echo [ERROR] esptool.exe not found under %ESPOOL%
  goto :fail
)
echo  esptool: %ESPT%
echo  Uploading to %COM% at 115200 (full image) ...
"%ESPT%" --chip esp32 --port %COM% --baud 115200 write_flash 0x0 "%BUILD%\CameraWebServer.ino.merged.bin"
if errorlevel 1 (
  echo.
  echo  Upload failed. Retrying once at 115200 ...
  "%ESPT%" --chip esp32 --port %COM% --baud 115200 write_flash 0x0 "%BUILD%\CameraWebServer.ino.merged.bin"
  if errorlevel 1 goto :fail
)

echo.
echo  [OK] Upload finished.
echo   LEFT  = 192.168.0.137   RIGHT = 192.168.0.69
echo   Wait ~10s after the board reboots, then verify:
echo     python -m ar_glass.checkip 192.168.0.137
goto :end

:fail
echo.
echo  [FAIL] Upload failed.
echo   - Check the COM port and USB connection.
echo   - Bare boards: hold IO0, tap RST, release IO0, then retry.
echo   - Retry the script once (power cycle the board if needed).

:end
echo.
pause