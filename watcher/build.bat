@echo off
pip install -r requirements.txt
pyinstaller --onefile --windowed ^
    --hidden-import=win32print ^
    --hidden-import=win32ui ^
    --hidden-import=win32api ^
    --collect-all customtkinter ^
    --add-data ".source;.source" ^
    --name gtx4-watcher ^
    main.py
echo.
echo 빌드 완료: dist\gtx4-watcher.exe
pause
