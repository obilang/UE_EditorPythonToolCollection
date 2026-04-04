@echo off
setlocal EnableDelayedExpansion

echo.
echo =====================================================
echo  Unreal Python Tools - Environment Setup
echo =====================================================
echo.

:: --------------------------------------------------------
:: Locate setup_config.ini next to this bat file
:: --------------------------------------------------------
set "SCRIPT_DIR=%~dp0"
set "CONFIG=%SCRIPT_DIR%setup_config.ini"

if not exist "%CONFIG%" (
    echo [ERROR] setup_config.ini not found at:
    echo         %CONFIG%
    echo.
    echo Please make sure setup_config.ini is in the same folder as this bat file.
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: Parse UnrealEnginePath from the [Setup] section
:: --------------------------------------------------------
set "UE_ENGINE_PATH="

for /f "usebackq tokens=1,* delims==" %%A in ("%CONFIG%") do (
    set "KEY=%%A"
    set "VAL=%%B"
    :: Trim leading spaces from key
    set "KEY=!KEY: =!"
    if /i "!KEY!"=="UnrealEnginePath" (
        :: Trim leading/trailing spaces from value
        for /f "tokens=* delims= " %%C in ("!VAL!") do set "UE_ENGINE_PATH=%%C"
    )
)

if "%UE_ENGINE_PATH%"=="" (
    echo [ERROR] UnrealEnginePath is not set in setup_config.ini.
    echo.
    echo Please open setup_config.ini and fill in the path to your Unreal Engine,
    echo for example:
    echo   UnrealEnginePath=D:\GameDev\UE_5.7\Engine
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: Verify UE Python exists
:: --------------------------------------------------------
set "UE_PYTHON=%UE_ENGINE_PATH%\Binaries\ThirdParty\Python3\Win64\python.exe"

if not exist "%UE_PYTHON%" (
    echo [ERROR] Unreal Engine Python not found at:
    echo         %UE_PYTHON%
    echo.
    echo Please verify that UnrealEnginePath in setup_config.ini is correct.
    echo Expected layout: ^<UnrealEnginePath^>\Binaries\ThirdParty\Python3\Win64\python.exe
    pause
    exit /b 1
)

echo Using UE Python: %UE_PYTHON%
echo.

:: --------------------------------------------------------
:: Run the Python setup script
:: --------------------------------------------------------
set "SETUP_PY=%SCRIPT_DIR%setup.py"

if not exist "%SETUP_PY%" (
    echo [ERROR] setup.py not found at:
    echo         %SETUP_PY%
    pause
    exit /b 1
)

"%UE_PYTHON%" "%SETUP_PY%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Setup script exited with error code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
endlocal
