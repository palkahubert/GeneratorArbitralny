@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SCRIPT=%SCRIPT_DIR%xsdb_set_config.tcl"
set "XSCT="

if defined XILINX_SDK (
  if exist "%XILINX_SDK%\bin\xsct.bat" set "XSCT=%XILINX_SDK%\bin\xsct.bat"
)

if not defined XSCT (
  if exist "C:\Xilinx\SDK\2018.3\bin\xsct.bat" set "XSCT=C:\Xilinx\SDK\2018.3\bin\xsct.bat"
)

if not defined XSCT (
  if exist "C:\Xilinx\Vivado\2018.3\bin\xsct.bat" set "XSCT=C:\Xilinx\Vivado\2018.3\bin\xsct.bat"
)

if not defined XSCT (
  for /f "delims=" %%I in ('where xsct.bat 2^>nul') do (
    set "XSCT=%%I"
    goto :found_xsct
  )
)

:found_xsct
if not defined XSCT (
  echo Could not find xsct.bat.
  echo Open "Xilinx SDK 2018.3 Command Prompt" and run:
  echo xsct "%SCRIPT%"
  pause
  exit /b 1
)

echo Running:
echo "%XSCT%" "%SCRIPT%"
echo.
"%XSCT%" "%SCRIPT%"
echo.
pause
