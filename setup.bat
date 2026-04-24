@echo off
echo Installing dependencies...
pip install -r requirements.txt
pip install selenium webdriver-manager
echo.
echo Setup complete. Run start.bat to launch the API.
pause
