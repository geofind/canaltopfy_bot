@echo off
setlocal
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set EXE=%~dp0run_worker.bat
set ICO=%~dp0topfy.ico

if exist "%STARTUP%\TopfyWorker.lnk" (
    echo Atalho de inicializacao ja existe.
) else (
    echo Criando atalho na pasta Inicializar do Windows...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$W = New-Object -ComObject WScript.Shell; $S = $W.CreateShortcut('%STARTUP%\TopfyWorker.lnk'); $S.TargetPath = '%EXE%'; $S.WorkingDirectory = (Split-Path '%EXE%'); $S.WindowStyle = 7; $S.IconLocation = '%ICO%,0'; $S.Save()"
    if errorlevel 1 (
        echo.
        echo FALHOU ao criar o atalho de inicializacao. Copie manualmente
        echo "%EXE%" para a pasta:
        echo   %STARTUP%
        pause
        exit /b 1
    )
)

echo Iniciando o worker agora...
start "" /min "%EXE%"

echo.
echo Worker LIGADO - vai iniciar sozinho toda vez que voce entrar no Windows.
echo Log em: %~dp0worker.log
pause
