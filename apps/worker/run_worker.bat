@echo off
title TopfyWorkerConsole
cd /d "%~dp0"
"C:\Python314\python.exe" -u _local_bootstrap.py >> worker.log 2>&1
