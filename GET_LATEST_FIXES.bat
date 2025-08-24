@echo off
echo ========================================
echo   BOJIM BOQ - GET LATEST FIXES
echo ========================================
echo.
echo This will update your local files with the latest fixes
echo including the working drawing upload interface.
echo.
pause

echo Updating from GitHub...
git pull origin devin/1755952240-automated-boq-system

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   UPDATE SUCCESSFUL!
    echo ========================================
    echo.
    echo The latest fixes have been downloaded:
    echo - Fixed drawing upload interface
    echo - Added missing API endpoint
    echo - Enhanced authentication
    echo - Cost estimation with configurable rates
    echo.
    echo You can now run Start_Bojim_BOQ.bat to test
    echo the working drawing upload functionality.
    echo.
) else (
    echo.
    echo ========================================
    echo   UPDATE FAILED
    echo ========================================
    echo.
    echo Please check your internet connection and try again.
    echo If problems persist, contact support.
    echo.
)

pause
