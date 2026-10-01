@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 goto NO_PYTHON

if not "%~1"=="" goto RUN_ARGS

:MENU
cls
echo ============================================================
echo           L1J Headless - Playable MVP 啟動器
echo ============================================================
echo.
echo  [1] 進入遊戲 (真實節奏 1.0x) - 直接按 Enter 預設
echo  [2] 進入遊戲 (快速倍速 2.0x)
echo  [3] 進入遊戲 (極速瞬時 Instant)
echo  [4] 觀看自動演示 (Demo 模式)
echo  [5] 執行全套回歸測試 (13 Tests)
echo  [Q] 離開
echo.
echo ============================================================
set /p MODE="請輸入選項 [1]: "

if "%MODE%"=="" goto OPT1
if "%MODE%"=="1" goto OPT1
if "%MODE%"=="2" goto OPT2
if "%MODE%"=="3" goto OPT3
if "%MODE%"=="4" goto OPT4
if "%MODE%"=="5" goto OPT5
if /i "%MODE%"=="Q" goto QUIT
goto OPT1

:OPT1
echo.
echo >>> 啟動真實節奏遊玩...
python mvp.py
goto END

:OPT2
echo.
echo >>> 啟動 2.0 倍速遊玩...
python mvp.py --speed 2.0
goto END

:OPT3
echo.
echo >>> 啟動極速瞬時遊玩...
python mvp.py --instant
goto END

:OPT4
echo.
echo >>> 啟動自動演示模式...
python mvp.py --demo --s007
goto END

:OPT5
echo.
echo >>> 執行測試套件...
python -m unittest tests/test_scenarios.py
goto END

:RUN_ARGS
python mvp.py %*
goto END

:NO_PYTHON
echo [錯誤] 找不到 Python，請先安裝 Python 並將其加入系統 PATH 環境變數。
goto END

:END
echo.
echo ============================================================
echo 程式已結束。
echo ============================================================
pause
exit /b 0

:QUIT
exit /b 0
