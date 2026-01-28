@echo on
setlocal

set "OSGEO4W_ROOT=C:\Users\Juan David Alonso\AppData\Local\Programs\OSGeo4W"

REM 1) Load GDAL/PROJ/Python env (NON-interactive)
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

REM 2) Go to the folder with your .tif files
cd /d "D:\M2_MoSEF\Acclim\DataCollection\data\JRC_flood_depth_maps\2021\events_touched"
REM 3) Quick check
gdalinfo --version

REM 4) Run the Python pipeline (stored in DataCollection root)
"%OSGEO4W_ROOT%\bin\python.exe" "D:\M2_MoSEF\Acclim\DataCollection\pipeline_cog.py"

pause
endlocal