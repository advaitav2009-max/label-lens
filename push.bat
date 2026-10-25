@echo off
echo ========================================================
echo Label Lens - Push to GitHub
echo ========================================================
echo Target: https://github.com/advaitav2009-max/label-lens.git
echo.
"%~dp0..\mingit\cmd\git.exe" push origin main
if %errorlevel% neq 0 (
    echo.
    echo Retrying with system git...
    git push origin main
)
echo.
echo ========================================================
echo Push complete! Vercel will auto-deploy the changes.
echo ========================================================
pause
