# Watcher 모듈 상세 설계

> 작성일: 2026-03-18
> 참고: dps-store-printer/watcher, BCMDCMD 분석 문서

## 1. 개요

로컬 폴더를 감시하여 PDF 파일이 생성되면 자동으로 B-Equip 프린터에 출력하는 모듈이다.
dps-store-printer/watcher의 검증된 패턴을 기반으로 하되, 가먼트 프린터 특성에 맞게 확장한다.

### 핵심 원칙

- **1차 출력**: win32print 직접 출력 (드라이버 기본 설정 사용, 구현 단순)
- **확장 출력**: BCMDCMD.exe 경유 (가먼트 전용 설정이 필요한 경우)
- GUI에서 두 가지 출력 모드를 선택할 수 있도록 설계

---

## 2. 데이터 흐름

### win32print 직접 출력 (기본)

```
[watch 폴더에 PDF 생성/이동]
        ↓ watchdog 감지
[파일 안정성 확인] (쓰기 완료 대기)
        ↓
[PDF → 이미지 변환] (pdf2image + poppler)
        ↓ 페이지별 PIL.Image 생성
[이미지 리사이즈] (프린터 물리 크기 기준)
        ↓
[win32print 출력] (프린터 DC에 직접 렌더링)
        ↓
[done 폴더 이동] 성공 / [error 폴더 이동] 실패
```

### BCMDCMD.exe 경유 출력 (확장)

```
[watch 폴더에 PDF 생성/이동]
        ↓ watchdog 감지
[파일 안정성 확인]
        ↓
[PDF → PNG 변환] (pdf2image)
        ↓ 임시 PNG 파일 저장
[XML 설정 생성] (xml_builder)
        ↓
[BCMDCMD.exe print] → ARX4 파일 생성
        ↓
[BCMDCMD.exe send] → 프린터 전송
        ↓ 임시 파일 정리 (PNG, XML, ARX4)
[done 폴더 이동] 성공 / [error 폴더 이동] 실패
```

---

## 3. 모듈 구조

```
equip-sync-b-module/
├── main.py                # 진입점
├── gui.py                 # GUI (Watcher 탭 + BCMDCMD 탭)
├── config.py              # 설정 관리
├── config.ini             # 사용자 설정
├── watcher.py             # 폴더 감시 (watchdog)
├── processor.py           # PDF 처리 파이프라인
├── printer.py             # win32print 직접 출력
├── gtx4cmd.py             # BCMDCMD.exe CLI 래퍼
├── xml_builder.py         # BCMDCMD용 XML 설정 생성
├── requirements.txt
├── build.bat
└── .source/
    ├── BCMDCMD.exe
    └── BCMDApi.dll
```

---

## 4. 모듈 상세

### 4-1. config.ini

```ini
[printer]
name = B-Equip           # Windows 프린터명 (제어판 > 장치 및 프린터)
mode = direct                   # direct: win32print 직접 / gtx4cmd: BCMDCMD.exe 경유

[gtx4cmd]
platen_size = 0                 # 0: 16x21, 1: 16x18, 2: 14x16, 3: 10x12, 4: 7x8
ink = 0                         # 0: Color Only, 1: White Only, 2: Color+White, 3: Black Only
copies = 1                      # 인쇄 매수
position = 00000000             # 인쇄 위치 (8자리, 앞4=좌측, 뒤4=상단, 단위 0.1mm)
white_as = 0                    # 0: RGB(255,255,255)를 투명으로, 1: 화이트로

[folder]
watch =                         # 감시 폴더 (비어있으면 ./watch)
done =                          # 완료 폴더 (비어있으면 ./done)
error =                         # 에러 폴더 (비어있으면 ./error)

[render]
dpi = 300                       # PDF → 이미지 변환 해상도

[poppler]
path =                          # poppler 경로 (비어있으면 시스템 PATH 또는 번들)
```

### 4-2. config.py

```python
"""설정 관리 - config.ini 로드 및 경로 처리"""

import configparser
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(
    sys.argv[0] if getattr(sys, "frozen", False) else __file__
))

_ini = configparser.ConfigParser()
_ini.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")

# --- printer ---
PRINTER_NAME = _ini.get("printer", "name", fallback="B-Equip")
PRINTER_MODE = _ini.get("printer", "mode", fallback="direct")  # direct / gtx4cmd

# --- gtx4cmd ---
PLATEN_SIZE  = _ini.getint("gtx4cmd", "platen_size", fallback=0)
INK          = _ini.getint("gtx4cmd", "ink", fallback=0)
COPIES       = _ini.getint("gtx4cmd", "copies", fallback=1)
POSITION     = _ini.get("gtx4cmd", "position", fallback="00000000")
WHITE_AS     = _ini.getint("gtx4cmd", "white_as", fallback=0)

# --- folder ---
WATCH_DIR = _ini.get("folder", "watch", fallback="") or os.path.join(BASE_DIR, "watch")
DONE_DIR  = _ini.get("folder", "done", fallback="")  or os.path.join(BASE_DIR, "done")
ERROR_DIR = _ini.get("folder", "error", fallback="") or os.path.join(BASE_DIR, "error")

# --- render ---
RENDER_DPI = _ini.getint("render", "dpi", fallback=300)

# --- poppler ---
def _resolve_poppler():
    explicit = _ini.get("poppler", "path", fallback="")
    if explicit:
        return explicit
    bundled = os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), "poppler")
    if os.path.isdir(bundled):
        return bundled
    return None  # 시스템 PATH 사용

POPPLER_PATH = _resolve_poppler()

# --- gtx4cmd exe ---
BCMDCMD_EXE = os.path.join(BASE_DIR, ".source", "BCMDCMD.exe")

# 폴더 자동 생성
for d in (WATCH_DIR, DONE_DIR, ERROR_DIR):
    os.makedirs(d, exist_ok=True)
```

### 4-3. watcher.py

```python
"""폴더 감시 - PDF 파일 생성/이동 이벤트 감지 및 처리"""

import logging
import os
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import config
from processor import process_file

logger = logging.getLogger(__name__)

# 파일 안정성 확인 파라미터
_STABLE_INTERVAL = 1.0   # 체크 간격 (초)
_STABLE_COUNT = 2         # 연속 동일 크기 횟수
_STABLE_TIMEOUT = 30.0    # 최대 대기 (초)
_APPEAR_TIMEOUT = 5.0     # 파일 출현 대기 (rename 딜레이)


class LabelFileHandler(FileSystemEventHandler):
    def __init__(self):
        self._processing: set[str] = set()
        self._lock = threading.Lock()

    def on_created(self, event):
        if not event.is_directory:
            self._try_process(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._try_process(event.dest_path)

    def _try_process(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext != ".pdf":
            return
        with self._lock:
            if path in self._processing:
                return
            self._processing.add(path)
        t = threading.Thread(target=self._wait_and_process, args=(path,), daemon=True)
        t.start()

    def _wait_and_process(self, path: str):
        try:
            if not self._wait_for_stable(path):
                logger.warning("파일 안정화 실패: %s", os.path.basename(path))
                return
            logger.info("처리 시작: %s", os.path.basename(path))
            process_file(path)
        except Exception:
            logger.exception("처리 실패: %s", os.path.basename(path))
        finally:
            with self._lock:
                self._processing.discard(path)

    def _wait_for_stable(self, path: str) -> bool:
        """파일 쓰기 완료 대기 (크기가 연속으로 동일하면 안정)"""
        deadline = time.time() + _STABLE_TIMEOUT

        # 파일 출현 대기 (Windows rename 딜레이 대응)
        appear_deadline = time.time() + _APPEAR_TIMEOUT
        while not os.path.exists(path):
            if time.time() > appear_deadline:
                return False
            time.sleep(0.2)

        prev_size = -1
        stable = 0
        while time.time() < deadline:
            if not os.path.exists(path):
                return False
            size = os.path.getsize(path)
            if size == prev_size and size > 0:
                stable += 1
                if stable >= _STABLE_COUNT:
                    return True
            else:
                stable = 0
            prev_size = size
            time.sleep(_STABLE_INTERVAL)
        return False


def start_watching() -> Observer:
    """폴더 감시 시작, Observer 반환"""
    observer = Observer()
    observer.schedule(LabelFileHandler(), config.WATCH_DIR, recursive=False)
    observer.daemon = True
    observer.start()
    logger.info("폴더 감시 시작: %s", config.WATCH_DIR)
    return observer
```

### 4-4. processor.py

```python
"""PDF 처리 파이프라인 - 출력 모드에 따라 분기"""

import logging
import os
import shutil
import tempfile

from pdf2image import convert_from_path
from PIL import Image

import config

logger = logging.getLogger(__name__)


def process_file(file_path: str):
    """PDF 파일 처리 → 출력 → done/error 이동"""
    try:
        if config.PRINTER_MODE == "gtx4cmd":
            _process_via_gtx4cmd(file_path)
        else:
            _process_via_direct(file_path)
        _move_to(file_path, config.DONE_DIR)
        logger.info("완료: %s", os.path.basename(file_path))
    except Exception as e:
        logger.error("실패: %s - %s", os.path.basename(file_path), e)
        _move_to(file_path, config.ERROR_DIR)


def _process_via_direct(file_path: str):
    """win32print 직접 출력"""
    from printer import print_image

    images = convert_from_path(
        file_path,
        dpi=config.RENDER_DPI,
        poppler_path=config.POPPLER_PATH,
    )
    for i, img in enumerate(images):
        logger.info("  페이지 %d/%d 출력 중...", i + 1, len(images))
        print_image(img, config.PRINTER_NAME)


def _process_via_gtx4cmd(file_path: str):
    """BCMDCMD.exe 경유 출력"""
    from gtx4cmd import create_arx4, send_to_printer
    from xml_builder import build_xml

    images = convert_from_path(
        file_path,
        dpi=config.RENDER_DPI,
        poppler_path=config.POPPLER_PATH,
    )
    tmp_dir = tempfile.mkdtemp(prefix="gtx4_")
    try:
        xml_path = os.path.join(tmp_dir, "settings.xml")
        build_xml(xml_path)

        for i, img in enumerate(images):
            png_path = os.path.join(tmp_dir, f"page_{i}.png")
            arx4_path = os.path.join(tmp_dir, f"page_{i}.arx4")
            img.save(png_path, "PNG")

            logger.info("  페이지 %d/%d ARX4 생성 중...", i + 1, len(images))
            rc = create_arx4(xml_path, png_path, arx4_path, config.POSITION)
            if rc != 0:
                raise RuntimeError(f"ARX4 생성 실패 (코드: {rc})")

            logger.info("  페이지 %d/%d 프린터 전송 중...", i + 1, len(images))
            rc = send_to_printer(arx4_path, config.PRINTER_NAME)
            if rc != 0:
                raise RuntimeError(f"프린터 전송 실패 (코드: {rc})")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _move_to(file_path: str, dest_dir: str):
    """파일을 대상 폴더로 이동 (이름 충돌 시 넘버링)"""
    name = os.path.basename(file_path)
    dest = os.path.join(dest_dir, name)
    counter = 1
    base, ext = os.path.splitext(name)
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{base}_{counter}{ext}")
        counter += 1
    shutil.move(file_path, dest)
```

### 4-5. printer.py

```python
"""win32print 직접 출력 - dps-store-printer/watcher 패턴"""

import win32print
import win32ui
from PIL import Image, ImageWin


def print_image(image: Image.Image, printer_name: str = None):
    """PIL 이미지를 Windows 프린터로 직접 출력"""
    if printer_name is None:
        printer_name = win32print.GetDefaultPrinter()

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    try:
        pw = hdc.GetDeviceCaps(110)  # PHYSICALWIDTH
        ph = hdc.GetDeviceCaps(111)  # PHYSICALHEIGHT

        # 이미지를 프린터 너비에 맞춰 비율 유지 리사이즈
        ratio = pw / image.width
        new_w = pw
        new_h = int(image.height * ratio)
        if new_h > ph:
            ratio = ph / image.height
            new_w = int(image.width * ratio)
            new_h = ph

        hdc.StartDoc("BCMD Print")
        hdc.StartPage()
        dib = ImageWin.Dib(image)
        dib.draw(hdc.GetHandleOutput(), (0, 0, new_w, new_h))
        hdc.EndPage()
        hdc.EndDoc()
    finally:
        hdc.DeleteDC()
```

### 4-6. gtx4cmd.py

```python
"""BCMDCMD.exe CLI 래퍼"""

import logging
import subprocess

import config

logger = logging.getLogger(__name__)

RETURN_CODES = {
    0: "성공",
    -1001: "드라이버 파일 없음",
    -1403: "프린터를 찾을 수 없거나 드라이버 사용 불가",
    -2001: "PNG 파일이 아니거나 로드 불가",
    -2401: "프린터 미발견 또는 LAN 미연결",
    -3102: "XML 파일 없음",
    -3103: "이미지 파일 없음",
    -3104: "-P와 -A 동시 지정 불가",
}


def _run(args: list[str]) -> int:
    """BCMDCMD.exe 실행, 리턴 코드 반환"""
    cmd = [config.BCMDCMD_EXE] + args
    logger.debug("실행: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    rc = result.returncode
    if rc != 0:
        desc = RETURN_CODES.get(rc, f"알 수 없는 에러 ({rc})")
        logger.error("BCMDCMD 에러: %s", desc)
    return rc


def create_arx4(xml_path: str, image_path: str, arx4_path: str, position: str) -> int:
    """PNG + XML → ARX4 생성"""
    return _run([
        "print",
        "-X", xml_path,
        "-I", image_path,
        "-A", arx4_path,
        "-L", position,
    ])


def send_to_printer(arx4_path: str, printer_name: str) -> int:
    """ARX4 → 프린터 전송"""
    return _run(["send", "-A", arx4_path, "-P", printer_name])


def get_status(printer_name: str, status_csv: str = None,
               option_csv: str = None, maint_csv: str = None) -> int:
    """프린터 상태 CSV 출력 (LAN 전용)"""
    args = ["status", "-P", printer_name]
    if status_csv:
        args += ["-S", status_csv]
    if option_csv:
        args += ["-O", option_csv]
    if maint_csv:
        args += ["-M", maint_csv]
    return _run(args)


def circulation(printer_name: str) -> int:
    """화이트 잉크 순환 (LAN 전용)"""
    return _run(["Circulation", "-P", printer_name])


def auto_cleaning(printer_name: str) -> int:
    """자동 클리닝 (LAN 전용)"""
    return _run(["AutoCleaning", "-P", printer_name])


def print_disable(printer_name: str) -> int:
    """인쇄 버튼 비활성화 (LAN 전용)"""
    return _run(["PrintDisable", "-P", printer_name])


def print_enable(printer_name: str) -> int:
    """인쇄 버튼 활성화 (LAN 전용)"""
    return _run(["PrintEnable", "-P", printer_name])


def menu_lock(printer_name: str) -> int:
    """메뉴 잠금 (LAN 전용)"""
    return _run(["MenuLock", "-P", printer_name])


def menu_unlock(printer_name: str) -> int:
    """메뉴 해제 (LAN 전용)"""
    return _run(["MenuUnlock", "-P", printer_name])


def get_log(printer_name: str, log_path: str) -> int:
    """프린터 로그 다운로드 (LAN 전용)"""
    return _run(["getlog", "-P", printer_name, "-L", log_path])


def pick_log(log_path: str, print_csv: str = None,
             oper_csv: str = None, maint_csv: str = None,
             start: str = None, end: str = None) -> int:
    """로그에서 이력 CSV 추출"""
    args = ["picklog", "-L", log_path]
    if print_csv:
        args += ["-P", print_csv]
    if oper_csv:
        args += ["-O", oper_csv]
    if maint_csv:
        args += ["-M", maint_csv]
    if start:
        args += ["-S", start]
    if end:
        args += ["-E", end]
    return _run(args)
```

### 4-7. xml_builder.py

```python
"""BCMDCMD.exe용 인쇄 설정 XML 생성"""

import xml.etree.ElementTree as ET

import config


def build_xml(output_path: str, **overrides):
    """config.ini 기반 + 오버라이드로 인쇄 설정 XML 생성"""
    root = ET.Element("GTOPTION")

    settings = {
        "szFileName": "",
        "uiCopies": str(overrides.get("copies", config.COPIES)),
        "byMachineMode": "0",
        "byPlatenSize": str(overrides.get("platen_size", config.PLATEN_SIZE)),
        "byInk": str(overrides.get("ink", config.INK)),
        "byResolution": "1",
    }

    for tag, value in settings.items():
        el = ET.SubElement(root, tag)
        el.text = value

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
```

---

## 5. GUI 설계

### 5-1. Watcher 탭

```
┌─────────────────────────────────────────────────┐
│ 상태: ● 감시 중                [시작] [정지]    │
├─────────────────────────────────────────────────┤
│ 프린터:    B-Equip                        │
│ 출력 모드: direct (win32print 직접)             │
│ 감시 폴더: C:\gtx4\watch                        │
│ 완료 폴더: C:\gtx4\done                         │
│ 렌더 DPI:  300                                  │
├─────────────────────────────────────────────────┤
│ 로그                                            │
│ 15:30:01 [INFO] 폴더 감시 시작: C:\gtx4\watch   │
│ 15:30:15 [INFO] 처리 시작: order_001.pdf         │
│ 15:30:16 [INFO]   페이지 1/2 출력 중...          │
│ 15:30:17 [INFO]   페이지 2/2 출력 중...          │
│ 15:30:17 [INFO] 완료: order_001.pdf              │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 5-2. BCMDCMD 탭

> 방식 C 확장 시 추가. 별도 문서로 상세 설계 예정.

---

## 6. 에러 처리

### 파일 처리 에러

| 상황                        | 처리                           |
| --------------------------- | ------------------------------ |
| PDF 변환 실패               | error 폴더로 이동, 로그 기록   |
| 프린터 연결 실패            | error 폴더로 이동, 로그 기록   |
| 파일 안정화 타임아웃 (30초) | 로그 경고, 건너뜀              |
| 파일명 충돌                 | `_1`, `_2` 등 넘버링 자동 부여 |

### BCMDCMD.exe 에러 (gtx4cmd 모드)

| 리턴 코드 | 의미                          | 대응                     |
| --------- | ----------------------------- | ------------------------ |
| 0         | 성공                          | 정상 처리                |
| -1403     | 프린터 미발견 / 드라이버 불가 | error 이동 + 사용자 알림 |
| -2001     | PNG 아님 / 로드 불가          | error 이동               |
| -2401     | LAN 미연결                    | error 이동 + 사용자 알림 |
| 기타 음수 | BCMDCMD 에러                  | error 이동 + 코드 로깅   |

---

## 7. 빌드

### requirements.txt

```
watchdog
pdf2image
Pillow
pywin32
customtkinter
pyinstaller
```

### build.bat

```bat
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
echo 빌드 완료: dist\gtx4-watcher.exe
pause
```

---

## 8. 배포 구성

```
gtx4-watcher/
├── gtx4-watcher.exe       # PyInstaller 빌드 결과
├── config.ini              # 사용자 설정 (현장에서 편집)
├── .source/
│   ├── BCMDCMD.exe         # B-Corp 제공
│   └── BCMDApi.dll         # B-Corp 제공
├── watch/                  # 감시 폴더 (자동 생성)
├── done/                   # 완료 폴더 (자동 생성)
└── error/                  # 에러 폴더 (자동 생성)
```

### 현장 설치 순서

1. B-Equip 프린터 드라이버 설치
2. 프린터 LAN/USB 연결 확인
3. `gtx4-watcher` 폴더 복사
4. `config.ini`에서 프린터명 확인/수정
5. `gtx4-watcher.exe` 실행
6. watch 폴더에 PDF 파일 넣어서 테스트
