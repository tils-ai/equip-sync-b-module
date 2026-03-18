# B-Equip 연동 모듈 설계안

> 작성일: 2026-03-18
> 수정일: 2026-03-18
> 참고: dps-store-printer (watcher / agent)

## 배경

jarvis 서버에 저장된 PDF를 받아와 B-Equip 가먼트 프린터로 출력하는 모듈이 필요하다.
dps-store-printer 프로젝트의 구조를 참고하여 세 가지 방식을 설계한다.

### 출력 방식 비교

| | BCMDCMD.exe 경유 | win32print 직접 |
|---|---|---|
| 파이프라인 | PDF → PNG → XML → ARX4 → 전송 (2단계 CLI) | PDF → 이미지 → 프린터 DC 직접 출력 |
| 장점 | 플래튼, 잉크 조합 등 가먼트 전용 설정 동적 제어 | 구현 단순, dps-store 패턴 재사용 |
| 단점 | 중간 파일 많음 (PNG, XML, ARX4) | 가먼트 전용 설정은 드라이버 기본값에 의존 |

> BCMDCMD.exe는 GUI 없는 순수 CLI 도구이다.
> 가먼트 전용 설정을 코드에서 동적 제어할 필요가 없다면, 드라이버 기본 설정 + win32print 직접 출력이 가장 간단하다.

---

## 방식 A: Watcher (폴더 감시 + win32print)

### 개요

로컬 폴더를 감시하여 PDF 파일이 생성되면 자동으로 B-Equip 프린터에 출력한다.
dps-store-printer/watcher와 동일한 방식. win32print로 직접 출력하며 드라이버 기본 설정을 사용한다.

> 상세 설계: [20260318-watcher-spec.md](./20260318-watcher-spec.md)

### 데이터 흐름

```
[jarvis 서버 / 외부 프로세스]
        ↓ PDF 파일 저장
[watch 폴더]
        ↓ watchdog 감지
[파일 안정성 확인]
        ↓
[PDF → 이미지 변환] (pdf2image)
        ↓
[win32print] → 프린터 직접 출력
        ↓
[done 폴더 이동] 또는 [error 폴더 이동]
```

### 장점

- 구현이 가장 단순함 (dps-store-printer/watcher 패턴 재사용)
- jarvis 외 다른 시스템에서도 PDF만 떨어뜨리면 사용 가능
- 오프라인에서도 동작 (로컬 파일 기반)
- 네트워크 장애에 강함

### 단점

- jarvis 서버와의 직접 통신 없음 (인쇄 상태 보고 불가)
- PDF를 감시 폴더에 가져다 놓는 별도 프로세스 필요
- 가먼트 전용 설정(잉크 조합 등)은 드라이버 기본값에 의존

---

## 방식 B: Agent (서버 폴링)

### 개요

jarvis 서버 API를 주기적으로 폴링하여 대기 중인 인쇄 작업을 가져오고,
PDF를 다운로드하여 B-Equip 프린터로 출력한 뒤 결과를 서버에 보고한다.
출력은 win32print 직접 방식을 기본으로 하되, BCMDCMD.exe 옵션도 지원 가능.

### 데이터 흐름

```
[jarvis 서버 API]
        ↓ 폴링 (GET /api/printer/jobs?status=pending)
[대기 작업 수신]
        ↓
[PDF 다운로드] (URL에서 fetch)
        ↓
[PDF → 이미지 변환] (pdf2image)
        ↓
[win32print] → 프린터 직접 출력
        ↓
[결과 보고] (POST /api/printer/jobs/{id}/printed 또는 /failed)
```

### 장점

- jarvis 서버와 양방향 통신 (상태 보고 가능)
- 인쇄 완료/실패를 서버에서 추적 가능
- 별도 파일 전달 프로세스 불필요 (서버가 직접 관리)

### 단점

- jarvis 서버 API 의존 (서버 장애 시 인쇄 불가)
- 네트워크 연결 필수
- jarvis API 스펙이 확정되어야 구현 가능

---

## 방식 C: Watcher + BCMDCMD GUI (확장)

### 개요

방식 A(폴더 감시 자동 출력)에 BCMDCMD.exe의 모든 기능을 GUI로 제공하는 탭을 추가한다.
BCMDCMD.exe는 CLI만 제공하므로, 이 모듈이 GUI 래퍼 역할을 겸한다.

### GUI 구조

```
┌──────────────────────────────────────────────────┐
│                 B-Equip Manager            │
├───────────┬──────────────────────────────────────┤
│ Watcher   │  BCMDCMD                             │
│ 탭        │  탭                                  │
├───────────┼──────────────────────────────────────┤
│           │                                      │
│ 폴더 감시 │  [인쇄 데이터 생성]                  │
│ 자동 출력 │   XML 파일: [선택]                   │
│ 시작/정지 │   PNG 파일: [선택]                   │
│           │   출력: ○ 프린터 ○ ARX4 파일         │
│ ───────── │   위치/크기: [____]                  │
│           │   [ARX4 생성]                        │
│ 상태: ● 실│                                      │
│ 프린터: BG│  [프린터 전송]                       │
│ 감시: ./wa│   ARX4 파일: [선택]                  │
│           │   프린터: [선택▼]                    │
│ ───────── │   [전송]                             │
│           │                                      │
│ [로그 뷰어│  [프린터 제어] (LAN 전용)            │
│  ........]│   프린터: [선택▼]                    │
│  ........]│   [잉크순환] [자동클리닝]            │
│  ........]│   [인쇄버튼 OFF/ON]                  │
│           │   [메뉴 잠금/해제]                   │
│           │                                      │
│           │  [상태 조회] (LAN 전용)              │
│           │   프린터: [선택▼]                    │
│           │   [상태 조회] → 결과 표시            │
│           │   잉크 잔량, 에러, 펌웨어 등         │
│           │                                      │
│           │  [로그 분석]                         │
│           │   [로그 다운로드]                    │
│           │   [이력 추출] → CSV 출력             │
│           │                                      │
└───────────┴──────────────────────────────────────┘
```

### BCMDCMD 탭 기능 목록

| 섹션 | 기능 | BCMDCMD 명령 |
|------|------|-------------|
| 인쇄 데이터 생성 | XML+PNG → ARX4 변환 | `print -X -I -A/-P -L -S/-R -W` |
| 프린터 전송 | ARX4 → 프린터 출력 | `send -A -P` |
| 데이터 추출 | ARX4 → XML/PNG 추출 | `extract -A -X -I -S` |
| 프린터 제어 | 잉크순환, 클리닝, 버튼/메뉴 제어 | `Circulation`, `AutoCleaning`, `PrintDisable/Enable`, `MenuLock/Unlock` |
| 상태 조회 | 프린터 상태/옵션/유지보수 정보 | `status -P -S -O -M` |
| 로그 다운로드 | 프린터 로그 파일 획득 | `getlog -P -L` |
| 로그 분석 | 인쇄/운영/유지보수 이력 CSV 추출 | `picklog -L -P -O -M -S -E` |

### 장점

- 방식 A의 자동 출력 + BCMDCMD.exe 전체 기능을 하나의 앱으로 통합
- BCMDCMD.exe에 없는 GUI를 제공하여 운영 편의성 향상
- 프린터 상태 모니터링, 유지보수 이력 분석 등 관리 도구로 활용
- 가먼트 전용 설정을 GUI에서 동적으로 조작 가능

### 단점

- 구현 범위가 가장 넓음
- BCMDCMD.exe의 모든 리턴 코드 핸들링 필요

---

## 모듈 구조 (방식 C 기준, 최대 범위)

```
equip-sync-b-module/
├── main.py                # 진입점 (GUI 실행)
├── gui.py                 # CustomTkinter GUI (탭 구조)
├── config.py              # 설정 관리 (config.ini 로드)
├── config.ini             # 사용자 설정
├── watcher.py             # 폴더 감시 (watchdog)
├── processor.py           # PDF → 이미지 변환 + 출력 파이프라인
├── printer.py             # win32print 직접 출력
├── gtx4cmd.py             # BCMDCMD.exe CLI 래퍼 (subprocess)
├── xml_builder.py         # 인쇄 설정 XML 생성 (BCMDCMD용)
├── requirements.txt       # 의존성
├── build.bat              # PyInstaller 빌드
├── .source/               # BCMDCMD.exe, BCMDApi.dll
└── docs/
```

### 의존성 (requirements.txt)

```
watchdog               # 폴더 감시
pdf2image              # PDF → 이미지 변환
Pillow                 # 이미지 처리
pywin32                # Windows 프린터 API
customtkinter          # GUI
pyinstaller            # EXE 빌드
```

> Agent 방식 추가 시: `requests` (HTTP 클라이언트)

---

## 구현 우선순위 권장

| 순서 | 내용 | 이유 |
|------|------|------|
| 1 | **방식 A: Watcher** 구현 | win32print 직접 출력로 프린터 연동 빠르게 검증 |
| 2 | **방식 C: BCMDCMD 탭** 추가 | CLI 도구의 GUI 래퍼로 운영 편의성 확보 |
| 3 | **방식 B: Agent** 추가 | jarvis API 스펙 확정 후 폴링 모듈 추가 |

---

## dps-store-printer 대비 주요 차이점

| 항목 | dps-store-printer | equip-sync-b-module |
|------|-------------------|---------------------|
| 프린터 | SLK TS200 (열전사 라벨) | B-Equip (가먼트) |
| 출력 방식 | win32print 직접 | win32print 직접 + BCMDCMD.exe (가먼트 설정 시) |
| 이미지 입력 | PNG만 | PNG (PDF에서 변환) |
| 서버 | store.dpl.shop | jarvis |
| 추가 기능 | - | BCMDCMD.exe GUI 래퍼 (상태 조회, 유지보수, 로그 분석) |
