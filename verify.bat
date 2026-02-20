@echo off
cd /d "%~dp0"
python -m py_compile app.py && echo APP_OK || echo APP_FAIL
python -m py_compile pages\home.py && echo HOME_OK || echo HOME_FAIL
python -m py_compile pages\script_execution.py && echo EXEC_OK || echo EXEC_FAIL
python -m py_compile pages\results_viewer.py && echo RESULTS_OK || echo RESULTS_FAIL
python -m py_compile pages\history.py && echo HISTORY_OK || echo HISTORY_FAIL
python -m py_compile config.py && echo CONFIG_OK || echo CONFIG_FAIL
echo DONE
