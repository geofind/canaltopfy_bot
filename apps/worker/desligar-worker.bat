@echo off
setlocal
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

echo Parando a execucao atual...
taskkill /F /T /FI "WINDOWTITLE eq TopfyWorkerConsole*" >nul 2>&1

if exist "%STARTUP%\TopfyWorker.lnk" (
    del "%STARTUP%\TopfyWorker.lnk"
    echo Atalho de inicializacao removido - nao inicia mais sozinho.
) else (
    echo Atalho de inicializacao ja nao existia.
)

echo.
echo Worker DESLIGADO. Rode ligar-worker.bat quando quiser voltar a rodar.
pause
