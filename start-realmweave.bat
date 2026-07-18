@echo off
REM ============================================================
REM  Realmweave launcher
REM  Starts BOTH servers this project needs, then opens the map:
REM    1. WebSocket game server  -> port 8765  (the living world)
REM    2. Static file server     -> port 8080  (serves docs/map.html)
REM  Close either spawned window to stop that server.
REM ============================================================

title Realmweave launcher
set "ROOT=%~dp0"

REM 1. Game server - run from backend so saves land in backend\data
start "Realmweave game server (8765)" cmd /k "cd /d %ROOT%backend && py run_server.py"

REM 2. Map static server - run from docs so map.html sits at the URL root
start "Realmweave map server (8080)" cmd /k "cd /d %ROOT%docs && py -m http.server 8080"

REM 3. Wait for the static server to bind, then open the map
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8080/map.html"

exit
