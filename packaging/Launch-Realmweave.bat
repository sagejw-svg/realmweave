@echo off
rem Realmweave launcher: start the local world server, then the game client.
setlocal
set HERE=%~dp0

rem Start the server minimized (it keeps running while you play).
start "Realmweave Server" /min "%HERE%RealmweaveServer.exe"

rem Give the server a moment to bind its port, then launch the client.
timeout /t 2 /nobreak >nul
start "Realmweave" "%HERE%RealmweaveClient.exe"

endlocal
