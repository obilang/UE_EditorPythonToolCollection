@echo off
setlocal EnableDelayedExpansion

echo.
echo =====================================================
echo  Unreal Python Tools - Update Python Libs
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
    set "KEY=!KEY: =!"
    if /i "!KEY!"=="UnrealEnginePath" (
        for /f "tokens=* delims= " %%C in ("!VAL!") do set "UE_ENGINE_PATH=%%C"
    )
)

if "%UE_ENGINE_PATH%"=="" (
    echo [ERROR] UnrealEnginePath is not set in setup_config.ini.
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
    pause
    exit /b 1
)

echo Using UE Python: %UE_PYTHON%
echo.

:: --------------------------------------------------------
:: Verify lib_requirements.txt exists
:: --------------------------------------------------------
set "REQS=%SCRIPT_DIR%lib_requirements.txt"

if not exist "%REQS%" (
    echo [ERROR] lib_requirements.txt not found at:
    echo         %REQS%
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: Run pip install --upgrade into Libs folder
:: --------------------------------------------------------
set "LIBS_DIR=%SCRIPT_DIR%Libs"

echo Installing / upgrading packages from lib_requirements.txt...
echo Target directory: %LIBS_DIR%
echo.

"%UE_PYTHON%" -m pip install --upgrade --target "%LIBS_DIR%" -r "%REQS%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] pip install failed with error code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Packages updated successfully.
echo.
pause
endlocal
