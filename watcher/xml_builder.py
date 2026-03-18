"""GTX4CMD.exe용 인쇄 설정 XML 생성."""

import xml.etree.ElementTree as ET

import config


def build_xml(output_path: str, **overrides):
    """config.ini 기반 + 오버라이드로 인쇄 설정 XML 생성.

    overrides로 전달 가능한 키:
        copies, platen_size, ink, white_as 등
    """
    root = ET.Element("GTOPTION")

    elements = {
        "szFileName": "",
        "uiCopies": str(overrides.get("copies", config.COPIES)),
        "byMachineMode": "0",
        "byPlatenSize": str(overrides.get("platen_size", config.PLATEN_SIZE)),
        "byInk": str(overrides.get("ink", config.INK)),
        "byResolution": "1",
    }

    for tag, value in elements.items():
        el = ET.SubElement(root, tag)
        el.text = value

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
