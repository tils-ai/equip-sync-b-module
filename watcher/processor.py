import logging
import os
import shutil
import tempfile

from pdf2image import convert_from_path

import config

logger = logging.getLogger(__name__)


def process_file(file_path: str):
    """PDF 파일 처리 → 출력 모드에 따라 분기 → done/error 이동."""
    os.makedirs(config.DONE_DIR, exist_ok=True)
    os.makedirs(config.ERROR_DIR, exist_ok=True)

    filename = os.path.basename(file_path)

    try:
        if config.PRINTER_MODE == "gtx4cmd":
            _process_via_gtx4cmd(file_path)
        else:
            _process_via_direct(file_path)

        dest = _unique_path(os.path.join(config.DONE_DIR, filename))
        shutil.move(file_path, dest)
        logger.info("완료 → %s", os.path.basename(dest))

    except Exception:
        logger.exception("처리 실패: %s", filename)
        dest = _unique_path(os.path.join(config.ERROR_DIR, filename))
        try:
            shutil.move(file_path, dest)
        except Exception:
            logger.exception("에러 폴더 이동 실패: %s", filename)


def _process_via_direct(file_path: str):
    """win32print 직접 출력."""
    from printer import print_image

    images = convert_from_path(
        file_path,
        dpi=config.RENDER_DPI,
        poppler_path=config.POPPLER_PATH,
    )
    for i, img in enumerate(images, 1):
        logger.info("  페이지 %d/%d 출력 중...", i, len(images))
        print_image(img)


def _process_via_gtx4cmd(file_path: str):
    """GTX4CMD.exe 경유 출력."""
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
            rc = create_arx4(xml_path, png_path, arx4_path)
            if rc != 0:
                raise RuntimeError(f"ARX4 생성 실패 (코드: {rc})")

            logger.info("  페이지 %d/%d 프린터 전송 중...", i + 1, len(images))
            rc = send_to_printer(arx4_path)
            if rc != 0:
                raise RuntimeError(f"프린터 전송 실패 (코드: {rc})")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _unique_path(path: str) -> str:
    """동일 파일명 충돌 시 번호를 붙여 고유 경로 반환."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{base}_{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1
