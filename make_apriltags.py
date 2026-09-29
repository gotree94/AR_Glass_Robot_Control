# -*- coding: utf-8 -*-
"""
AprilTag 6세트 생성기 (헤드마운트 ESP32-CAM 2개 + 손/팔 태그)

용도
    카메라 2개가 좌/우 관자놀이에 붙어 있을 때, 같은 카메라가
    자신의 좌/우 손을 구분해서 추적할 수 있도록 태그를 6개 만든다.
    동일한 ID를 양쪽에 두면 좌/우를 구분할 수 없으므로 ID를 모두 다르게 배정한다.

    L1 / R1 : 엄지 쪽 검지
    L2 / R2 : 손등 또는 엄지 측면
    L3 / R3 : 팔꿈치 쪽 손바닥면 전완

사용법
    python make_apriltags.py

출력 (바탕화면 apriltags_output 폴더)
    tags/                 개별 태그 PNG (300 DPI, 실제 크기)
    sheet_LEFT.png        왼쪽 3장 인쇄용 A4
    sheet_RIGHT.png       오른쪽 3장 인쇄용 A4
    preview.png           6개 한눈에 보기
    verify_report.txt     탐지 검증 결과
    tags_meta.json        ID / 크기 / 부착위치 (검출 설정용)

주의
    - 인쇄는 반드시 "실제 크기 100%" 로 할 것.
    - 태그 바깥 흰 여백(quiet zone)을 자르지 말 것.
    - AprilTag C 라이브러리 / OpenCV 모두 family = tag36h11 로 설정할 것.
      (주의: OpenCV 의 DICT_ARUCO_MIP_36H12 는 tag36h12 가 아니므로 사용하지 말 것.
       최신 apriltag 라이브러리에는 tag36h12 자체가 없고 tag36h11 / tag36h10 만 있다.)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FAMILY = "tag36h11"
DICT_ID = cv2.aruco.DICT_APRILTAG_36H11
GRID = 6
BLACK_BORDER = 1
TOTAL_CELLS = GRID + 2 * BLACK_BORDER
DPI = 300
PX_PER_MM = DPI / 25.4
QUIET_CELLS = 1.5
PAGE_MM = (210.0, 297.0)
MARGIN_MM = 12.0

DESKTOP = Path.home() / "Desktop"
OUT_DIR = DESKTOP / "apriltags_output"
TAG_DIR = OUT_DIR / "tags"


@dataclass
class TagSpec:
    label: str
    tag_id: int
    size_mm: float
    mount_en: str
    mount_ko: str


TAGS = [
    TagSpec("L1", 0, 20.0, "index_finger_thumb_side", "엄지 쪽 검지"),
    TagSpec("L2", 1, 30.0, "hand_back_or_thumb_side", "손등 또는 엄지 측면"),
    TagSpec("L3", 2, 40.0, "forearm_palmar_near_elbow", "팔꿈치 쪽 손바닥면 전완"),
    TagSpec("R1", 3, 20.0, "index_finger_thumb_side", "엄지 쪽 검지"),
    TagSpec("R2", 4, 30.0, "hand_back_or_thumb_side", "손등 또는 엄지 측면"),
    TagSpec("R3", 5, 40.0, "forearm_palmar_near_elbow", "팔꿈치 쪽 손바닥면 전완"),
]

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def mm(value: float) -> int:
    return int(round(value * PX_PER_MM))


def pick_font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_tag(tag_id: int, size_mm: float):
    """(8x8 패턴 incl. black border) 을 셀 단위로 확대하고 흰 여백을 붙인다."""
    base = cv2.aruco.generateImageMarker(
        cv2.aruco.getPredefinedDictionary(DICT_ID), tag_id, TOTAL_CELLS
    )
    cell_px = max(6, int(round(mm(size_mm) / TOTAL_CELLS)))
    tag_px = cell_px * TOTAL_CELLS
    body = cv2.resize(base, (tag_px, tag_px), interpolation=cv2.INTER_NEAREST)
    quiet_px = int(round(cell_px * QUIET_CELLS))
    canvas = np.full((tag_px + 2 * quiet_px, tag_px + 2 * quiet_px), 255, np.uint8)
    canvas[quiet_px:quiet_px + tag_px, quiet_px:quiet_px + tag_px] = body
    return canvas, cell_px, quiet_px, tag_px


def dashed_rect(draw: ImageDraw.ImageDraw, box, dash, width, color):
    x0, y0, x1, y1 = box
    for x in range(x0, x1, dash * 2):
        draw.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=width)
        draw.line([(x, y1), (min(x + dash, x1), y1)], fill=color, width=width)
    for y in range(y0, y1, dash * 2):
        draw.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=width)
        draw.line([(x1, y), (x1, min(y + dash, y1))], fill=color, width=width)


def draw_ruler(draw: ImageDraw.ImageDraw, x, y, length_mm, font, color=(0, 0, 0)):
    length_px = mm(length_mm)
    draw.line([(x, y), (x + length_px, y)], fill=color, width=2)
    for t in range(0, length_mm + 1):
        tx = x + mm(t)
        h = mm(6) if t % 10 == 0 else (mm(4) if t % 5 == 0 else mm(2))
        draw.line([(tx, y), (tx, y - h)], fill=color, width=2 if t % 10 == 0 else 1)
    for t in range(0, length_mm + 1, 10):
        draw.text((x + mm(t), y + mm(3)), str(t), fill=color, font=font)
    draw.text((x + length_px + mm(3), y - mm(6)), "mm", fill=color, font=font)


def save_tag(spec: TagSpec, array: np.ndarray) -> Path:
    img = Image.fromarray(array, mode="L")
    path = TAG_DIR / f"{spec.label}_id{spec.tag_id:02d}_{spec.size_mm:.0f}mm.png"
    img.save(path, dpi=(DPI, DPI))
    return path


def render_sheet(side: str, entries, fonts) -> Path:
    page_w, page_h = mm(PAGE_MM[0]), mm(PAGE_MM[1])
    sheet = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    f_title, f_label, f_body, f_small, f_ruler = fonts

    m = mm(MARGIN_MM)
    draw.text((m, m), f"AprilTag {FAMILY} - {side} hand / arm", fill=(0, 0, 0), font=f_title)
    draw.text(
        (m, m + mm(11)),
        "100% actual size printing required. Do not crop the white margin.",
        fill=(60, 60, 60),
        font=f_body,
    )

    y = m + mm(22)
    for spec, array, cell_px, quiet_px, tag_px in entries:
        block_h = array.shape[0] + mm(34)
        img = Image.fromarray(array, mode="L").convert("RGB")
        x = m
        sheet.paste(img, (x, y))
        dashed_rect(
            draw,
            (x - mm(2), y - mm(2), x + array.shape[1] + mm(2), y + array.shape[0] + mm(2)),
            mm(1.2),
            2,
            (170, 170, 170),
        )
        ty = y + array.shape[0] + mm(4)
        draw.text(
            (x, ty),
            f"{spec.label}   id={spec.tag_id}   {spec.size_mm:.0f} mm",
            fill=(0, 0, 0),
            font=f_label,
        )
        draw.text((x, ty + mm(8)), spec.mount_ko, fill=(40, 40, 40), font=f_body)
        draw.text(
            (x, ty + mm(14)),
            f"cell {cell_px}px / {DPI}dpi / quiet zone {QUIET_CELLS} cell",
            fill=(110, 110, 110),
            font=f_small,
        )
        y += block_h

    draw_ruler(draw, m, page_h - m - mm(22), 50, f_ruler)
    draw.text(
        (m, page_h - m - mm(4)),
        "Ruler must measure exactly 50 mm. If not, fix the print scale before mounting.",
        fill=(60, 60, 60),
        font=f_small,
    )
    path = OUT_DIR / f"sheet_{side}.png"
    sheet.save(path, dpi=(DPI, DPI))
    return path


def render_preview(rendered) -> Path:
    pad = mm(6)
    cols = 3
    rows = 2
    cw = max(a.shape[1] for _, a, _, _, _ in rendered) + 2 * pad
    ch = max(a.shape[0] for _, a, _, _, _ in rendered) + 2 * pad + mm(8)
    canvas = Image.new("RGB", (cw * cols, ch * rows), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)
    f = pick_font(mm(4))
    for i, (spec, array, _, _, _) in enumerate(rendered):
        cx = (i % cols) * cw + pad
        cy = (i // cols) * ch + pad
        canvas.paste(Image.fromarray(array, mode="L").convert("RGB"), (cx, cy))
        draw.text(
            (cx, cy + array.shape[0] + mm(1)),
            f"{spec.label} / id {spec.tag_id} / {spec.size_mm:.0f}mm",
            fill=(0, 0, 0),
            font=f,
        )
    path = OUT_DIR / "preview.png"
    canvas.save(path, dpi=(DPI, DPI))
    return path


def verify(rendered):
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(DICT_ID), cv2.aruco.DetectorParameters()
    )
    lines = []
    for spec, array, cell_px, quiet_px, tag_px in rendered:
        head = f"{spec.label} id={spec.tag_id} size={tag_px / PX_PER_MM:.1f}mm :"
        for scale in (1.0, 0.6, 0.35, 0.2):
            small = cv2.resize(array, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if scale < 1.0:
                small = cv2.GaussianBlur(small, (3, 3), 0.6)
            _, ids, _ = detector.detectMarkers(small)
            ok = ids is not None and len(ids) == 1 and int(ids[0][0]) == spec.tag_id
            width_px = int(round(tag_px * scale))
            lines.append(f"  {head} scale {scale:>4}  width {width_px:>4}px  {'OK' if ok else 'FAIL'}")
    return lines


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TAG_DIR.mkdir(parents=True, exist_ok=True)

    fonts = (
        pick_font(mm(6)),
        pick_font(mm(5)),
        pick_font(mm(4)),
        pick_font(mm(3)),
        pick_font(mm(3.5)),
    )

    rendered = []
    meta = []
    for spec in TAGS:
        array, cell_px, quiet_px, tag_px = build_tag(spec.tag_id, spec.size_mm)
        path = save_tag(spec, array)
        rendered.append((spec, array, cell_px, quiet_px, tag_px))
        meta.append(
            {
                "label": spec.label,
                "tag_id": spec.tag_id,
                "family": FAMILY,
                "size_mm": spec.size_mm,
                "actual_size_mm": round(tag_px / PX_PER_MM, 2),
                "cell_px": cell_px,
                "mount": spec.mount_en,
                "mount_ko": spec.mount_ko,
                "file": path.name,
            }
        )
        print(f"[tag] {spec.label} id={spec.tag_id} {tag_px / PX_PER_MM:.1f}mm -> {path.name}")

    left = [r for r in rendered if r[0].label.startswith("L")]
    right = [r for r in rendered if r[0].label.startswith("R")]
    print("[sheet]", render_sheet("LEFT", left, fonts).name)
    print("[sheet]", render_sheet("RIGHT", right, fonts).name)
    print("[image]", render_preview(rendered).name)

    report = verify(rendered)
    (OUT_DIR / "verify_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))

    (OUT_DIR / "tags_meta.json").write_text(
        json.dumps({"family": FAMILY, "dpi": DPI, "tags": meta}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
