import configparser
import os
import sys


def _base_dir():
    """exe 실행 시 exe가 있는 폴더, 스크립트 실행 시 스크립트 폴더 반환."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
INI_PATH = os.path.join(BASE_DIR, "config.ini")

_DEFAULT_INI = """\
[printer]
; Windows 설정 > 프린터에서 정확한 이름 확인
name = Brother GTX-4
; 출력 모드: direct (win32print 직접) / gtx4cmd (GTX4CMD.exe 경유)
mode = direct

[gtx4cmd]
; GTX4CMD.exe 경로 (비워두면 .source 폴더에서 탐색)
exe_path =
; 플래튼 크기: 0=16x21, 1=16x18, 2=14x16, 3=10x12, 4=7x8
platen_size = 0
; 잉크 조합: 0=Color Only, 1=White Only, 2=Color+White, 3=Black Only
ink = 0
; 인쇄 매수
copies = 1
; 인쇄 위치 (8자리, 앞4=좌측여백, 뒤4=상단여백, 단위 0.1mm)
position = 00000000
; RGB(255,255,255) 해석: 0=투명, 1=화이트
white_as = 0

[folder]
; 비워두면 exe와 같은 폴더 기준으로 자동 생성
watch =
done =
error =

[render]
; PDF → 이미지 변환 해상도 (높을수록 선명)
dpi = 300

[poppler]
; poppler 바이너리 경로 (비워두면 시스템 PATH 또는 번들)
path =
"""

# config.ini가 없으면 기본값으로 생성
if not os.path.exists(INI_PATH):
    with open(INI_PATH, "w", encoding="utf-8") as f:
        f.write(_DEFAULT_INI)

_ini = configparser.ConfigParser()
_ini.read(INI_PATH, encoding="utf-8")

# --- printer ---
PRINTER_NAME = _ini.get("printer", "name", fallback="Brother GTX-4")
PRINTER_MODE = _ini.get("printer", "mode", fallback="direct")

# --- gtx4cmd ---
PLATEN_SIZE = _ini.getint("gtx4cmd", "platen_size", fallback=0)
INK = _ini.getint("gtx4cmd", "ink", fallback=0)
COPIES = _ini.getint("gtx4cmd", "copies", fallback=1)
POSITION = _ini.get("gtx4cmd", "position", fallback="00000000")
WHITE_AS = _ini.getint("gtx4cmd", "white_as", fallback=0)

# --- gtx4cmd exe 경로 ---
def _resolve_gtx4cmd():
    explicit = _ini.get("gtx4cmd", "exe_path", fallback="")
    if explicit and os.path.isfile(explicit):
        return explicit
    # .source 폴더에서 탐색
    source = os.path.join(BASE_DIR, ".source", "GTX4CMD.exe")
    if os.path.isfile(source):
        return source
    # PyInstaller 번들
    bundled = os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), ".source", "GTX4CMD.exe")
    if os.path.isfile(bundled):
        return bundled
    return ""

GTX4CMD_EXE = _resolve_gtx4cmd()

# --- folder ---
WATCH_DIR = _ini.get("folder", "watch", fallback="") or os.path.join(BASE_DIR, "watch")
DONE_DIR = _ini.get("folder", "done", fallback="") or os.path.join(BASE_DIR, "done")
ERROR_DIR = _ini.get("folder", "error", fallback="") or os.path.join(BASE_DIR, "error")

# --- render ---
RENDER_DPI = _ini.getint("render", "dpi", fallback=300)

# --- poppler ---
def _resolve_poppler():
    explicit = _ini.get("poppler", "path", fallback="")
    if explicit:
        return explicit
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, "poppler")
        if os.path.isdir(bundled):
            return bundled
    return None

POPPLER_PATH = _resolve_poppler()

# 파일 안정성 확인 파라미터
FILE_STABLE_CHECK_INTERVAL = 1.0
FILE_STABLE_CHECK_COUNT = 2

# 폴더 자동 생성
for _d in (WATCH_DIR, DONE_DIR, ERROR_DIR):
    os.makedirs(_d, exist_ok=True)


def save_value(section: str, key: str, value: str):
    """config.ini에 값을 저장한다."""
    _ini.set(section, key, value)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)


def reload():
    """config.ini를 다시 읽어서 모듈 변수를 갱신한다."""
    global PRINTER_NAME, PRINTER_MODE, PLATEN_SIZE, INK, COPIES
    global POSITION, WHITE_AS, GTX4CMD_EXE
    global WATCH_DIR, DONE_DIR, ERROR_DIR, RENDER_DPI, POPPLER_PATH

    _ini.read(INI_PATH, encoding="utf-8")

    PRINTER_NAME = _ini.get("printer", "name", fallback="Brother GTX-4")
    PRINTER_MODE = _ini.get("printer", "mode", fallback="direct")
    PLATEN_SIZE = _ini.getint("gtx4cmd", "platen_size", fallback=0)
    INK = _ini.getint("gtx4cmd", "ink", fallback=0)
    COPIES = _ini.getint("gtx4cmd", "copies", fallback=1)
    POSITION = _ini.get("gtx4cmd", "position", fallback="00000000")
    WHITE_AS = _ini.getint("gtx4cmd", "white_as", fallback=0)
    GTX4CMD_EXE = _resolve_gtx4cmd()
    WATCH_DIR = _ini.get("folder", "watch", fallback="") or os.path.join(BASE_DIR, "watch")
    DONE_DIR = _ini.get("folder", "done", fallback="") or os.path.join(BASE_DIR, "done")
    ERROR_DIR = _ini.get("folder", "error", fallback="") or os.path.join(BASE_DIR, "error")
    RENDER_DPI = _ini.getint("render", "dpi", fallback=300)
    POPPLER_PATH = _resolve_poppler()

    for _d in (WATCH_DIR, DONE_DIR, ERROR_DIR):
        os.makedirs(_d, exist_ok=True)
