@echo off
echo ========================================================
echo Label Lens - Push to GitHub
echo ========================================================
echo Target: https://github.com/advaitav2009-max/label-lens.git
echo.
"%~dp0..\mingit\cmd\git.exe" push -u origin main
if %errorlevel% neq 0 (
    echo.
    echo Pushing with system git...
    git push -u origin main
)
echo.
pause
