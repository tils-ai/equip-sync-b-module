## 장비 연동 모듈 구현

### 프로젝트 개요

B-Corp 가먼트 프린터(B-Equip)와 연동하여 jarvis 서버의 PDF를 자동 출력하는 모듈.

### 현재 상태

- 장비 커맨드라인 도구(BCMDCMD.exe) 분석 완료
- Watcher 모듈 코드 구현 완료 (watcher/)
- GitHub Actions 빌드 파이프라인 구성 완료
- Agent 모듈은 jarvis API 스펙 확정 후 구현 예정

### 구조

```
equip-sync-b-module/
├── .source/               # BCMDCMD.exe, BCMDApi.dll (대외비, git 미추적)
├── .github/workflows/     # GitHub Actions 빌드
├── watcher/               # Watcher 모듈 (1차 구현)
│   ├── main.py            # 진입점
│   ├── gui.py             # CustomTkinter GUI + 설정 다이얼로그
│   ├── config.py          # config.ini 관리
│   ├── watcher.py         # 폴더 감시 (watchdog)
│   ├── processor.py       # PDF 처리 (direct/bcmd 분기)
│   ├── printer.py         # win32print 직접 출력
│   ├── gtx4cmd.py         # BCMDCMD.exe CLI 래퍼
│   ├── xml_builder.py     # 인쇄 설정 XML 생성
│   ├── requirements.txt
│   └── build.bat
└── docs/                  # 설계 문서
```

### 출력 모드

- `direct`: win32print로 프린터 DC 직접 출력 (기본, 드라이버 설정 사용)
- `gtx4cmd`: BCMDCMD.exe 경유 (PNG → XML → ARX4 → 전송, 가먼트 전용 설정 동적 제어)

config.ini `[printer] mode` 또는 GUI 설정에서 전환 가능.

### 설계 방향 (3단계)

1. **Watcher**: 폴더 감시 자동 출력 (완료)
2. **BCMDCMD GUI 탭**: CLI 도구의 GUI 래퍼 확장 (예정)
3. **Agent**: jarvis 서버 폴링 → PDF 다운로드 → 출력 → 결과 보고 (API 스펙 확정 후)

### 대외비 주의

- `.source/` 폴더의 exe, dll, PDF는 대외비 자료
- docs에서 장비명은 B-Equip / B-Corp / BCMD로 마스킹됨
- watcher/ 코드에는 실행에 필요한 실제 프린터명이 포함되어 있으나, exe/dll은 번들하지 않음
- 릴리즈 빌드에도 exe/dll 미포함 → 현장 PC에서 경로 지정 방식

### 참고 프로젝트

- `dps-store-printer/watcher`: 폴더 감시 패턴 원본
- `dps-store-printer/agent`: 서버 폴링 패턴 원본
