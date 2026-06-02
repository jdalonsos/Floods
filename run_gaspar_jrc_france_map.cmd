@echo off
setlocal
powershell.exe -ExecutionPolicy Bypass -File "%~dp0run_gaspar_jrc_france_map.ps1" %*
