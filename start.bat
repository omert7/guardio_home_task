@echo off
REM Start script for Pokemon Streaming Proxy with config validation

REM Set default config path if not provided
if "%POKEPROXY_CONFIG%"=="" set POKEPROXY_CONFIG=config.json

REM Display header
echo ====================================
echo Pokemon Streaming Proxy Service
echo ====================================
echo Config file: %POKEPROXY_CONFIG%

REM First validate the configuration file
echo.
echo Validating configuration file...
python validate_config.py

REM Check if validation was successful
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [31m❌ Config validation failed! Please fix the errors and try again.[0m
  exit /b 1
)

REM If we get here, validation was successful
echo.
echo [32m✅ Config validation passed! Starting service...[0m

REM Start the application
python run.py 