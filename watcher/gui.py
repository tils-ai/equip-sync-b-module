import ctypes
import logging
import queue
import sys

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import customtkinter as ctk

import config

logger = logging.getLogger(__name__)

# 컬러 팔레트
_BG = "#2C2C2E"
_FRAME_BG = "#3A3A3C"
_TEXT = "#E0DDD9"
_TEXT_MUTED = "#8E8A85"
_GREEN = "#8BC5A3"
_CORAL = "#D4897A"
_BLUE = "#7A9EB8"
_GRAY = "#5A5856"
_LOG_BG = "#333335"
_LOG_TEXT = "#D0CCC8"
_FONT = "Malgun Gothic"


class QueueHandler(logging.Handler):
    """로그를 큐로 전달하여 GUI에서 소비."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class WatcherApp(ctk.CTk):
    MAX_LOG_LINES = 1000

    def __init__(self):
        super().__init__()
        self.title("Brother GTX-4 Watcher")
        self.geometry("680x580")
        self.minsize(560, 440)
        self.configure(fg_color=_BG)

        ctk.set_appearance_mode("dark")

        self._log_queue = queue.Queue()
        self._observer = None
        self._running = False

        self._setup_logging()
        self._build_ui()
        self._poll_log_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 자동 시작
        self.after(200, self._start)

    # ─── 로깅 ───

    def _setup_logging(self):
        handler = QueueHandler(self._log_queue)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    # ─── UI 빌드 ───

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- 상태 바 ---
        status_frame = ctk.CTkFrame(self, fg_color=_FRAME_BG, corner_radius=8)
        status_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)

        self._status_dot = ctk.CTkLabel(
            status_frame, text="●", font=(_FONT, 16), text_color=_GRAY,
        )
        self._status_dot.grid(row=0, column=0, padx=(12, 4), pady=8)

        self._status_label = ctk.CTkLabel(
            status_frame, text="중지됨",
            font=(_FONT, 14, "bold"), text_color=_TEXT,
        )
        self._status_label.grid(row=0, column=1, sticky="w")

        # --- 설정 정보 ---
        info_frame = ctk.CTkFrame(self, fg_color=_FRAME_BG, corner_radius=8)
        info_frame.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)

        mode_display = "win32print 직접" if config.PRINTER_MODE == "direct" else "GTX4CMD.exe 경유"
        settings = [
            ("프린터", config.PRINTER_NAME),
            ("출력 모드", mode_display),
            ("감시 폴더", config.WATCH_DIR),
            ("완료 폴더", config.DONE_DIR),
            ("렌더 DPI", str(config.RENDER_DPI)),
        ]
        if config.PRINTER_MODE == "gtx4cmd":
            gtx4_path = config.GTX4CMD_EXE or "(미설정)"
            settings.append(("GTX4CMD 경로", gtx4_path))

        for i, (label, value) in enumerate(settings):
            ctk.CTkLabel(
                info_frame, text=label,
                font=(_FONT, 12), text_color=_TEXT_MUTED,
            ).grid(row=i, column=0, padx=(12, 8), pady=2, sticky="w")
            ctk.CTkLabel(
                info_frame, text=str(value), anchor="w",
                font=(_FONT, 12), text_color=_TEXT,
            ).grid(row=i, column=1, padx=(0, 12), pady=2, sticky="w")

        # --- 설정 버튼 ---
        settings_btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        settings_btn_frame.grid(row=2, column=0, padx=12, pady=(0, 6), sticky="ew")

        self._settings_btn = ctk.CTkButton(
            settings_btn_frame, text="⚙ 설정", command=self._open_settings,
            font=(_FONT, 12), fg_color=_GRAY, hover_color="#6B6360",
            corner_radius=8, width=80, height=28,
        )
        self._settings_btn.pack(side="right")

        # --- 로그 ---
        log_label = ctk.CTkLabel(
            self, text="로그", font=(_FONT, 12),
            text_color=_TEXT_MUTED, anchor="w",
        )
        log_label.grid(row=3, column=0, padx=14, pady=(6, 0), sticky="nw")

        self._log_text = ctk.CTkTextbox(
            self, state="disabled",
            font=(_FONT, 11),
            fg_color=_LOG_BG, text_color=_LOG_TEXT,
            corner_radius=8,
        )
        self._log_text.grid(row=3, column=0, padx=12, pady=(24, 6), sticky="nsew")

        # --- 시작/정지 버튼 ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=12, pady=(6, 12), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._start_btn = ctk.CTkButton(
            btn_frame, text="시작", command=self._start,
            font=(_FONT, 13), fg_color=_BLUE,
            hover_color="#6B8EA8", corner_radius=8,
        )
        self._start_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._stop_btn = ctk.CTkButton(
            btn_frame, text="중지", command=self._stop,
            font=(_FONT, 13), fg_color=_GRAY,
            hover_color="#6B6360", corner_radius=8, state="disabled",
        )
        self._stop_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    # ─── 상태 ───

    def _update_status(self):
        if self._running:
            self._status_dot.configure(text_color=_GREEN)
            self._status_label.configure(text="감시 중")
            self._start_btn.configure(state="disabled", fg_color=_GRAY)
            self._stop_btn.configure(state="normal", fg_color=_CORAL, hover_color="#C47A6B")
        else:
            self._status_dot.configure(text_color=_GRAY)
            self._status_label.configure(text="중지됨")
            self._start_btn.configure(state="normal", fg_color=_BLUE)
            self._stop_btn.configure(state="disabled", fg_color=_GRAY)

    # ─── 시작/정지 ───

    def _start(self):
        if self._running:
            return
        from watcher import start_watching
        self._observer = start_watching()
        self._running = True
        self._update_status()
        logger.info("=== Brother GTX-4 Watcher ===")
        logger.info("프린터: %s", config.PRINTER_NAME)
        logger.info("출력 모드: %s", config.PRINTER_MODE)
        logger.info("감시 폴더: %s", config.WATCH_DIR)

    def _stop(self):
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._running = False
        self._update_status()
        logger.info("감시 중지됨")

    # ─── 로그 폴링 ───

    def _poll_log_queue(self):
        has_new = False
        while not self._log_queue.empty():
            try:
                msg = self._log_queue.get_nowait()
                self._log_text.configure(state="normal")
                self._log_text.insert("end", msg + "\n")
                self._log_text.configure(state="disabled")
                has_new = True
            except queue.Empty:
                break

        if has_new:
            self._log_text.see("end")
            self._trim_log()

        self.after(100, self._poll_log_queue)

    def _trim_log(self):
        content = self._log_text.get("1.0", "end")
        lines = content.split("\n")
        if len(lines) > self.MAX_LOG_LINES:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", f"{len(lines) - self.MAX_LOG_LINES}.0")
            self._log_text.configure(state="disabled")

    # ─── 설정 다이얼로그 ───

    def _open_settings(self):
        SettingsDialog(self)

    # ─── 종료 ───

    def _on_closing(self):
        self._stop()
        self.destroy()


class SettingsDialog(ctk.CTkToplevel):
    """설정 편집 다이얼로그."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("설정")
        self.geometry("500x480")
        self.configure(fg_color=_BG)
        self.transient(parent)
        self.grab_set()
        self._parent = parent

        self.grid_columnconfigure(1, weight=1)

        row = 0

        # --- printer ---
        row = self._section_header("프린터", row)
        self._printer_name = self._entry_row("프린터명", config.PRINTER_NAME, row)
        row += 1
        self._printer_mode = self._combo_row(
            "출력 모드", ["direct", "gtx4cmd"], config.PRINTER_MODE, row,
        )
        row += 1

        # --- gtx4cmd ---
        row = self._section_header("GTX4CMD", row)
        self._exe_path = self._entry_row("exe 경로", config.GTX4CMD_EXE, row)
        row += 1

        browse_btn = ctk.CTkButton(
            self, text="찾기...", command=self._browse_exe,
            font=(_FONT, 11), fg_color=_GRAY, hover_color="#6B6360",
            width=60, height=24, corner_radius=6,
        )
        browse_btn.grid(row=row - 1, column=2, padx=(4, 12), pady=2)

        platen_options = ["0: 16x21", "1: 16x18", "2: 14x16", "3: 10x12", "4: 7x8"]
        current_platen = platen_options[config.PLATEN_SIZE] if config.PLATEN_SIZE < len(platen_options) else platen_options[0]
        self._platen_size = self._combo_row("플래튼 크기", platen_options, current_platen, row)
        row += 1

        ink_options = ["0: Color Only", "1: White Only", "2: Color+White", "3: Black Only"]
        current_ink = ink_options[config.INK] if config.INK < len(ink_options) else ink_options[0]
        self._ink = self._combo_row("잉크 조합", ink_options, current_ink, row)
        row += 1

        self._copies = self._entry_row("인쇄 매수", str(config.COPIES), row)
        row += 1
        self._position = self._entry_row("인쇄 위치", config.POSITION, row)
        row += 1

        # --- folder ---
        row = self._section_header("폴더", row)
        self._watch_dir = self._entry_row("감시 폴더", config.WATCH_DIR, row)
        row += 1
        self._done_dir = self._entry_row("완료 폴더", config.DONE_DIR, row)
        row += 1
        self._error_dir = self._entry_row("에러 폴더", config.ERROR_DIR, row)
        row += 1

        # --- render ---
        row = self._section_header("렌더링", row)
        self._render_dpi = self._entry_row("DPI", str(config.RENDER_DPI), row)
        row += 1

        # --- 저장 버튼 ---
        save_btn = ctk.CTkButton(
            self, text="저장", command=self._save,
            font=(_FONT, 13), fg_color=_BLUE,
            hover_color="#6B8EA8", corner_radius=8,
        )
        save_btn.grid(row=row, column=0, columnspan=3, padx=12, pady=12, sticky="ew")

    def _section_header(self, text: str, row: int) -> int:
        ctk.CTkLabel(
            self, text=text, font=(_FONT, 13, "bold"), text_color=_TEXT,
        ).grid(row=row, column=0, columnspan=2, padx=12, pady=(12, 4), sticky="w")
        return row + 1

    def _entry_row(self, label: str, value: str, row: int) -> ctk.CTkEntry:
        ctk.CTkLabel(
            self, text=label, font=(_FONT, 11), text_color=_TEXT_MUTED,
        ).grid(row=row, column=0, padx=(12, 8), pady=2, sticky="w")
        entry = ctk.CTkEntry(self, font=(_FONT, 11), fg_color=_LOG_BG, text_color=_TEXT)
        entry.grid(row=row, column=1, padx=(0, 12), pady=2, sticky="ew")
        entry.insert(0, value)
        return entry

    def _combo_row(self, label: str, values: list, current: str, row: int) -> ctk.CTkComboBox:
        ctk.CTkLabel(
            self, text=label, font=(_FONT, 11), text_color=_TEXT_MUTED,
        ).grid(row=row, column=0, padx=(12, 8), pady=2, sticky="w")
        combo = ctk.CTkComboBox(
            self, values=values, font=(_FONT, 11),
            fg_color=_LOG_BG, text_color=_TEXT, dropdown_fg_color=_FRAME_BG,
        )
        combo.grid(row=row, column=1, padx=(0, 12), pady=2, sticky="ew")
        combo.set(current)
        return combo

    def _browse_exe(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="GTX4CMD.exe 선택",
            filetypes=[("실행 파일", "*.exe"), ("모든 파일", "*.*")],
        )
        if path:
            self._exe_path.delete(0, "end")
            self._exe_path.insert(0, path)

    def _save(self):
        config.save_value("printer", "name", self._printer_name.get())
        config.save_value("printer", "mode", self._printer_mode.get())
        config.save_value("gtx4cmd", "exe_path", self._exe_path.get())
        config.save_value("gtx4cmd", "platen_size", self._platen_size.get().split(":")[0])
        config.save_value("gtx4cmd", "ink", self._ink.get().split(":")[0])
        config.save_value("gtx4cmd", "copies", self._copies.get())
        config.save_value("gtx4cmd", "position", self._position.get())
        config.save_value("folder", "watch", self._watch_dir.get())
        config.save_value("folder", "done", self._done_dir.get())
        config.save_value("folder", "error", self._error_dir.get())
        config.save_value("render", "dpi", self._render_dpi.get())

        config.reload()
        logger.info("설정 저장 완료 (재시작 시 적용)")
        self.destroy()
