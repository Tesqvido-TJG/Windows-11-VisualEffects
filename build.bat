@echo off
title Keyboard Effects - Build

echo.
echo ==========================================
echo       KEYBOARD EFFECTS - BUILD
echo ==========================================
echo.

echo [1/4] Cleaning old builds...

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [2/4] Installing required packages...

py -m pip install --upgrade pyinstaller
py -m pip install pygame pynput PyQt6

echo.
echo [3/4] Building EXE...

pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "KeyboardEffects" ^
    --icon "icon.ico" ^
    --add-data "sounds;sounds" ^
    --add-data "icon.ico;." ^
    main.py

echo.
echo [4/4] Build finished.
echo.

if exist "dist\KeyboardEffects.exe" (

    echo ==========================================
    echo              BUILD SUCCESS
    echo ==========================================
    echo.
    echo EXE:
    echo dist\KeyboardEffects.exe
    echo.

) else (

    echo ==========================================
    echo              BUILD FAILED
    echo ==========================================
    echo.
)

pause
