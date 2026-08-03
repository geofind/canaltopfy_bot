@echo off
title TopfyWorkerConsole
cd /d "%~dp0"
"C:\Python314\python.exe" _local_bootstrap.py >> worker.log 2>&1
