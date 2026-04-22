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
; 여러 개 지정 시 콤마 구분 (첫 번째 실패 시 다음 프린터로 자동 폴백)
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
; RGB(255,255,255) 해석: 0=투명, 1=화이트 잉크 (색있는 옷에서 흰 디자인 필요 시 1)
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

[api]
; dps-store 테넌트명 (인증 시 자동 설정)
tenant =
; API 키 (Device Auth로 발급, 자동 설정)
api_key =
; dps-store 서버 URL
base_url = https://store.dpl.shop
; 풀링 간격 (초)
poll_interval = 5

[download]
; PDF 다운로드 폴더 (비워두면 ./download)
dir =
"""

# config.ini가 없으면 기본값으로 생성
if not os.path.exists(INI_PATH):
    with open(INI_PATH, "w", encoding="utf-8") as f:
        f.write(_DEFAULT_INI)

_ini = configparser.ConfigParser()
_ini.read(INI_PATH, encoding="utf-8")

def _parse_printer_names(raw: str) -> list[str]:
    names = [n.strip() for n in raw.split(",") if n.strip()]
    return names or ["Brother GTX-4"]


# --- printer ---
PRINTER_NAMES = _parse_printer_names(_ini.get("printer", "name", fallback="Brother GTX-4"))
PRINTER_NAME = PRINTER_NAMES[0]  # 하위호환: 단일 참조 시 첫 번째 프린터
PRINTER_MODE = _ini.get("printer", "mode", fallback="direct")

# --- gtx4cmd ---
PLATEN_SIZE = _ini.getint("gtx4cmd", "platen_size", fallback=0)
INK = _ini.getint("gtx4cmd", "ink", fallback=0)
COPIES = _ini.getint("gtx4cmd", "copies", fallback=1)
POSITION = _ini.get("gtx4cmd", "position", fallback="00000000")
WHITE_AS = _ini.getint("gtx4cmd", "white_as", fallback=0)

# 플래튼 크기 (0.1mm 단위, 너비 x 높이) — 인치 → 25.4mm 환산
PLATEN_DIMS = {
    0: (4064, 5334),  # 16x21 inches
    1: (4064, 4572),  # 16x18 inches
    2: (3556, 4064),  # 14x16 inches
    3: (2540, 3048),  # 10x12 inches
    4: (1778, 2032),  # 7x8 inches
}

# --- gtx4cmd exe 경로 ---
def _resolve_gtx4cmd():
    explicit = _ini.get("gtx4cmd", "exe_path", fallback="")
    if explicit and os.path.isfile(explicit):
        return explicit
    # exe와 같은 폴더 (배포 시 기본)
    same_dir = os.path.join(BASE_DIR, "GTX4CMD.exe")
    if os.path.isfile(same_dir):
        return same_dir
    # .source 폴더 (개발 시)
    source = os.path.join(BASE_DIR, ".source", "GTX4CMD.exe")
    if os.path.isfile(source):
        return source
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

# --- api ---
API_TENANT = _ini.get("api", "tenant", fallback="")
API_KEY = _ini.get("api", "api_key", fallback="")
API_BASE_URL = _ini.get("api", "base_url", fallback="https://store.dpl.shop")
API_POLL_INTERVAL = _ini.getint("api", "poll_interval", fallback=5)

# --- download ---
DOWNLOAD_DIR = _ini.get("download", "dir", fallback="") or os.path.join(BASE_DIR, "download")

# 파일 안정성 확인 파라미터
FILE_STABLE_CHECK_INTERVAL = 1.0
FILE_STABLE_CHECK_COUNT = 2

# 폴더 자동 생성
for _d in (WATCH_DIR, DONE_DIR, ERROR_DIR, DOWNLOAD_DIR):
    os.makedirs(_d, exist_ok=True)


def save_value(section: str, key: str, value: str):
    """config.ini에 값을 저장한다."""
    _ini.set(section, key, value)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)


def reload():
    """config.ini를 다시 읽어서 모듈 변수를 갱신한다."""
    global PRINTER_NAME, PRINTER_NAMES, PRINTER_MODE, PLATEN_SIZE, INK, COPIES
    global POSITION, WHITE_AS, GTX4CMD_EXE
    global WATCH_DIR, DONE_DIR, ERROR_DIR, RENDER_DPI, POPPLER_PATH
    global API_TENANT, API_KEY, API_BASE_URL, API_POLL_INTERVAL, DOWNLOAD_DIR

    _ini.read(INI_PATH, encoding="utf-8")

    PRINTER_NAMES = _parse_printer_names(_ini.get("printer", "name", fallback="Brother GTX-4"))
    PRINTER_NAME = PRINTER_NAMES[0]
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

    API_TENANT = _ini.get("api", "tenant", fallback="")
    API_KEY = _ini.get("api", "api_key", fallback="")
    API_BASE_URL = _ini.get("api", "base_url", fallback="https://store.dpl.shop")
    API_POLL_INTERVAL = _ini.getint("api", "poll_interval", fallback=5)
    DOWNLOAD_DIR = _ini.get("download", "dir", fallback="") or os.path.join(BASE_DIR, "download")

    for _d in (WATCH_DIR, DONE_DIR, ERROR_DIR, DOWNLOAD_DIR):
        os.makedirs(_d, exist_ok=True)
