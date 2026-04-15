@echo off
cd /d "C:\Users\Hp\friday-ai"
start python server.py
timeout /t 3
powershell -command "Invoke-Item 'C:\Users\Hp\friday-ai\index.html'"
pause