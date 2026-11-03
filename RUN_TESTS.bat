@echo off
setlocal
rem ApoDesign test runner - double-click me.
rem It looks for your ComfyUI's own Python; if it cannot find it, it asks.

set "PY="
if exist "%~dp0..\..\..\python_embeded\python.exe" set "PY=%~dp0..\..\..\python_embeded\python.exe"
if defined PY goto run

echo.
echo Could not find ComfyUI's Python automatically.
echo Open the python_embeded folder of the ComfyUI you use, then DRAG the file
echo python.exe into this window and press Enter.
echo (example: D:\ComfyUI\ComfyUI_windows_apo1\python_embeded\python.exe)
echo.
set /p PY=Path: 
set PY=%PY:"=%
if exist "%PY%" goto run
echo.
echo That file was not found.
pause
exit /b 1

:run
echo Using: %PY%
echo.
"%PY%" "%~dp0tests\run_all.py"
echo.
echo Results were also saved to: %~dp0tests\test_results.txt
pause
