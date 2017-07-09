mkdir build
if errorlevel 1 exit 1

cd build
if errorlevel 1 exit 1

cmake -G "NMake Makefiles" ^
         -DCMAKE_BUILD_TYPE:STRING=RELEASE ^
         -DCMAKE_PREFIX_PATH=%LIBRARY_PREFIX% ^
         -DCMAKE_INSTALL_PREFIX:PATH=%LIBRARY_PREFIX% ^
         -DBUILD_STATIC_LIBS:BOOL=ON ^
         %SRC_DIR%
if errorlevel 1 exit 1

nmake
if errorlevel 1 exit 1

nmake install
if errorlevel 1 exit 1
