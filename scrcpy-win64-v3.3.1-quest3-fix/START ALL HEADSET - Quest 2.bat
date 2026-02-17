@echo off
setlocal enabledelayedexpansion

echo Detecting connected devices...
set count=0
set x_pos=0

REM Load CSV into memory (skip header line)
set csv_count=0
if exist devices.csv (
    for /f "skip=1 tokens=1,2 delims=," %%a in (devices.csv) do (
        set "serial_!csv_count!=%%a"
        set "name_!csv_count!=%%b"
        set /a csv_count+=1
    )
)

REM Process connected devices
for /f "tokens=1" %%a in ('.\adb.exe devices ^| findstr /r /v "List"') do (
    if not "%%a"=="" (
        set /a count+=1
        set /a x_pos=!count!*700
        
        REM Look up device name from CSV
        set "device_name=%%a"
        for /l %%i in (0,1,!csv_count!) do (
            if "!serial_%%i!"=="%%a" (
                set "device_name=!name_%%i!"
            )
        )
        
        echo Starting scrcpy for device: %%a ^(!device_name!^)
        start "scrcpy-%%a" /MAX .\scrcpy.exe -s %%a --crop 1080:900:270:270 --window-title "!device_name!"
        
        timeout /t 2 /nobreak >nul
    )
)

if !count!==0 (
    echo No devices found!
) else (
    echo Started scrcpy for !count! device(s)
)

pause