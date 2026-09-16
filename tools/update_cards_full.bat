@echo off
REM Full re-scan variant: re-checks the entire overall band (100-200), so it catches
REM new high-rated cards (123+) and anything the quick incremental scan skipped.
REM Slower (several minutes). Same commit+push behaviour as update_cards.bat.
set RENDERZ_FULL=1
call "%~dp0update_cards.bat"
