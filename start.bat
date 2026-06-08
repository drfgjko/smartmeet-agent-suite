@echo off
REM ============================================================================
REM  SmartMeet Agent Suite - Bootstrap Launcher (Pure ASCII, encoding-safe)
REM  This file intentionally contains NO Chinese characters to avoid GBK/UTF-8
REM  garbled text issues in cmd.exe. All user-facing messages are handled by
REM  the Python launcher (start_launcher.py) which controls its own encoding.
REM ============================================================================

REM -- Resolve the project root to the directory where this .bat file lives --
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

REM -- Try to find conda in PATH first --
where conda >nul 2>&1
if %ERRORLEVEL% equ 0 (
    goto :found_conda
)

REM -- Probe common Miniconda / Anaconda install locations --
set "CONDA_PROBE="
for %%P in (
    "%USERPROFILE%\miniconda3\Scripts\conda.exe"
    "%USERPROFILE%\Miniconda3\Scripts\conda.exe"
    "%USERPROFILE%\anaconda3\Scripts\conda.exe"
    "%USERPROFILE%\Anaconda3\Scripts\conda.exe"
    "C:\ProgramData\miniconda3\Scripts\conda.exe"
    "C:\ProgramData\Miniconda3\Scripts\conda.exe"
    "C:\ProgramData\anaconda3\Scripts\conda.exe"
    "C:\tools\miniconda3\Scripts\conda.exe"
    "D:\miniconda3\Scripts\conda.exe"
    "D:\Miniconda3\Scripts\conda.exe"
) do (
    if exist %%P (
        set "CONDA_PROBE=%%~P"
        goto :probe_done
    )
)
:probe_done

if defined CONDA_PROBE (
    REM Activate conda base so that 'conda run' is available
    for %%F in ("%CONDA_PROBE%") do set "CONDA_SCRIPTS_DIR=%%~dpF"
    call "%CONDA_SCRIPTS_DIR%activate.bat"
    goto :found_conda
)

REM -- conda not found at all --
echo [ERROR] conda was not found in PATH or common install locations.
echo         Please install Miniconda and add it to your system PATH.
echo         Download: https://docs.conda.io/en/latest/miniconda.html
echo.
echo Press any key to exit...
pause >nul
exit /b 1

:found_conda
REM -- Launch the Python startup orchestrator inside the smartmeet conda env --
conda run --no-capture-output -n smartmeet python "%PROJECT_ROOT%\start_launcher.py" %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Launcher exited with an error. See messages above.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
