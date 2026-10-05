# pip install opencv-contrib-python numpy pillow ezdxf


import cv2
import numpy as np
from PIL import Image
from pathlib import Path
import sys
import ezdxf


# ============================================================
# 기본 설정
# ============================================================

# AprilTag 종류
TAG_FAMILY = cv2.aruco.DICT_APRILTAG_36h11

# AprilTag ID
TAGS = {
    0: "RIGHT_1_THUMB_INDEX",
    1: "RIGHT_2_HAND",
    2: "RIGHT_3_FOREARM",

    3: "LEFT_1_THUMB_INDEX",
    4: "LEFT_2_HAND",
    5: "LEFT_3_FOREARM",
}

# PNG 해상도
DPI = 600

# AprilTag 내부 모듈 개수
# AprilTag 36h11은 8 x 8 모듈로 취급
TAG_GRID = 8

# ------------------------------------------------------------
# 흰색 여백(Quiet Zone) 설정
# ------------------------------------------------------------
# 태그(검은 테두리) 바깥쪽에 반드시 흰색으로 비워둬야 하는 폭
# module 단위 (1 module = 태그크기 / 8)
#   1.0 = 최소값 (이보다 작으면 인식률 급락)
#   1.5 ~ 2.0 = 권장 (ESP32-CAM처럼 해상도가 낮거나 비스듬히 볼 때)
QUIET_ZONE_MODULES = 1.0

# 가이드라인 표시 여부 (False 면 가이드 없이 흰 여백만 생성)
DRAW_GUIDE = True

# 가이드라인 바깥쪽 추가 여백 (mm) - 선과 안내 문구가 들어갈 공간
GUIDE_PAD_MM = 3.0

# PNG 가이드라인 색상 (B, G, R)
GUIDE_COLOR = (0, 0, 255)       # 빨강


# ============================================================
# 입력값 확인
# ============================================================

if len(sys.argv) != 2:

    print()
    print("사용법:")
    print("    python make_apriltag2.py 20")
    print()
    print("예:")
    print("    python make_apriltag2.py 20")
    print("    python make_apriltag2.py 50")
    print("    python make_apriltag2.py 100")
    print()

    sys.exit(1)


try:

    tag_size_mm = float(sys.argv[1])

except ValueError:

    print("오류: 크기는 숫자로 입력해야 합니다.")
    print()
    print("예:")
    print("    python make_apriltag2.py 20")

    sys.exit(1)


if tag_size_mm <= 0:

    print("오류: 태그 크기는 0보다 커야 합니다.")
    sys.exit(1)


# ============================================================
# 바탕화면 찾기
# ============================================================

desktop = Path.home() / "Desktop"

if not desktop.exists():

    desktop = Path.home() / "바탕 화면"


if not desktop.exists():

    desktop = Path.home()


# ============================================================
# 출력 폴더
# ============================================================

size_text = str(tag_size_mm).replace(".", "_")

output_dir = desktop / f"AprilTag_6개_{size_text}mm"

output_dir.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# AprilTag Dictionary
# ============================================================

aruco_dict = cv2.aruco.getPredefinedDictionary(
    TAG_FAMILY
)


# ============================================================
# PNG 해상도 / 여백 계산
# ============================================================

# 실제 mm → 600 DPI 픽셀
pixels_per_mm = DPI / 25.4

tag_pixels = int(
    round(tag_size_mm * pixels_per_mm)
)


# 너무 작은 이미지 방지
tag_pixels = max(tag_pixels, 100)


# 1 module 크기
module_mm = tag_size_mm / TAG_GRID
module_pixels = tag_pixels / TAG_GRID

# 흰색 여백(Quiet Zone) 폭
quiet_mm = module_mm * QUIET_ZONE_MODULES
quiet_pixels = int(round(quiet_mm * pixels_per_mm))

# 가이드 바깥 추가 여백
pad_mm = GUIDE_PAD_MM if DRAW_GUIDE else 0.0
pad_pixels = int(round(pad_mm * pixels_per_mm))

# PNG 한 장의 전체 크기 (정사각형)
image_pixels = tag_pixels + (quiet_pixels + pad_pixels) * 2

# 이미지 전체 실제 크기
image_mm = tag_size_mm + (quiet_mm + pad_mm) * 2


# ============================================================
# 가이드라인 그리기 도구 (PNG)
# ============================================================

def draw_dashed_line(img, p1, p2, color, thickness, dash, gap):

    x1, y1 = p1
    x2, y2 = p2

    length = float(np.hypot(x2 - x1, y2 - y1))

    if length == 0:
        return

    dx = (x2 - x1) / length
    dy = (y2 - y1) / length

    pos = 0.0

    while pos < length:

        end = min(pos + dash, length)

        cv2.line(
            img,
            (int(round(x1 + dx * pos)), int(round(y1 + dy * pos))),
            (int(round(x1 + dx * end)), int(round(y1 + dy * end))),
            color,
            thickness,
            cv2.LINE_AA
        )

        pos += dash + gap


def draw_dashed_rect(img, top_left, bottom_right, color,
                     thickness, dash, gap):

    x1, y1 = top_left
    x2, y2 = bottom_right

    draw_dashed_line(img, (x1, y1), (x2, y1), color, thickness, dash, gap)
    draw_dashed_line(img, (x2, y1), (x2, y2), color, thickness, dash, gap)
    draw_dashed_line(img, (x2, y2), (x1, y2), color, thickness, dash, gap)
    draw_dashed_line(img, (x1, y2), (x1, y1), color, thickness, dash, gap)


def draw_corner_marks(img, top_left, bottom_right, color,
                      length, thickness):

    x1, y1 = top_left
    x2, y2 = bottom_right

    cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness, cv2.LINE_AA)

    cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness, cv2.LINE_AA)

    cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness, cv2.LINE_AA)

    cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness, cv2.LINE_AA)


def fit_text(img, text, org_x, baseline_y, max_width, color,
             max_scale=0.7, thickness=1):
    """폭에 맞춰 글자 크기를 줄여가며 텍스트를 넣습니다."""

    scale = max_scale

    while scale > 0.2:

        (w, h), _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            thickness
        )

        if w <= max_width:
            break

        scale -= 0.05

    cv2.putText(
        img,
        text,
        (org_x, baseline_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA
    )


# ============================================================
# AprilTag 생성
# ============================================================

def create_tag_image(tag_id):

    image = cv2.aruco.generateImageMarker(
        aruco_dict,
        tag_id,
        tag_pixels
    )

    return image


# ============================================================
# 흰색 여백 + 가이드라인이 포함된 PNG 이미지 생성
# ============================================================

def create_tag_with_guide(tag_image):

    """
    구성 (바깥 → 안쪽):

        [가이드 바깥 여백] → [빨간 점선 = 흰색 영역 경계]
                          → [흰색 Quiet Zone]
                          → [AprilTag 검은 테두리]

    빨간 점선 안쪽(태그 바깥쪽)은 반드시 흰색으로 유지해야 합니다.
    """

    offset = quiet_pixels + pad_pixels

    canvas = np.full(
        (image_pixels, image_pixels, 3),
        255,
        dtype=np.uint8
    )

    canvas[
        offset:offset + tag_pixels,
        offset:offset + tag_pixels
    ] = cv2.cvtColor(tag_image, cv2.COLOR_GRAY2BGR)

    if not DRAW_GUIDE:
        return canvas

    # 선 두께 / 점선 간격은 해상도(600DPI)에 맞춰 mm 기준으로 계산
    thickness = max(2, int(round(0.2 * pixels_per_mm)))
    dash = max(8, int(round(1.5 * pixels_per_mm)))
    gap = max(5, int(round(0.9 * pixels_per_mm)))
    corner = max(15, int(round(2.5 * pixels_per_mm)))

    g1 = pad_pixels
    g2 = image_pixels - pad_pixels - 1

    # 흰색 영역의 바깥 경계 (점선)
    draw_dashed_rect(
        canvas,
        (g1, g1),
        (g2, g2),
        GUIDE_COLOR,
        thickness,
        dash,
        gap
    )

    # 모서리 표시 (실선)
    draw_corner_marks(
        canvas,
        (g1, g1),
        (g2, g2),
        GUIDE_COLOR,
        corner,
        thickness + 1
    )

    # 안내 문구 (선 바깥, 위쪽 여백)
    note = (
        f"KEEP WHITE: {QUIET_ZONE_MODULES:g} module"
        f" = {quiet_mm:.2f}mm"
    )

    fit_text(
        canvas,
        note,
        g1,
        max(pad_pixels - int(round(0.6 * pixels_per_mm)), 12),
        g2 - g1,
        GUIDE_COLOR
    )

    return canvas


# ============================================================
# PNG 저장
# ============================================================

def save_png(image, filepath):

    # 컬러(BGR)이면 RGB로 변환
    if image.ndim == 3:

        image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

    pil_image = Image.fromarray(image)

    # 실제 인쇄 크기 정보를 DPI로 저장
    pil_image.save(
        filepath,
        dpi=(DPI, DPI)
    )


# ============================================================
# DXF 생성
# ============================================================

def create_dxf(tag_id, filepath):

    """
    AprilTag를 실제 mm 단위의 DXF로 생성합니다.

    좌표 원점(0, 0) = 태그 왼쪽 아래 모서리

    레이어:
        TAG   : 태그 본체 (검은 module + 외곽선)
        GUIDE : 흰색 여백(Quiet Zone) 경계 점선 + 안내 문구
                (가공/인쇄 시 GUIDE 레이어는 끄거나 재단선으로 사용)

    AprilTag 36h11:
        8 x 8 module
    """

    # setup=True : DASHED 등 기본 선 종류를 불러옴
    doc = ezdxf.new(
        "R2010",
        setup=True
    )

    doc.layers.add(
        "TAG",
        color=7
    )

    doc.layers.add(
        "GUIDE",
        color=1,
        linetype="DASHED"
    )

    msp = doc.modelspace()

    module_size = tag_size_mm / TAG_GRID

    # 태그 이미지 생성
    image = create_tag_image(tag_id)

    # 8x8 module 중앙에서 색상 샘플
    height, width = image.shape

    for row in range(TAG_GRID):

        for col in range(TAG_GRID):

            # 각 module의 중심 픽셀
            px = int(
                (col + 0.5)
                * width
                / TAG_GRID
            )

            py = int(
                (row + 0.5)
                * height
                / TAG_GRID
            )

            value = image[py, px]

            # 검은색 module만 DXF에 생성
            if value < 128:

                x1 = col * module_size
                y1 = (
                    tag_size_mm
                    - (row + 1) * module_size
                )

                x2 = x1 + module_size
                y2 = y1 + module_size

                points = [
                    (x1, y1),
                    (x2, y1),
                    (x2, y2),
                    (x1, y2),
                    (x1, y1),
                ]

                msp.add_lwpolyline(
                    points,
                    close=True,
                    dxfattribs={"layer": "TAG"}
                )

    # 외곽선
    msp.add_lwpolyline(
        [
            (0, 0),
            (tag_size_mm, 0),
            (tag_size_mm, tag_size_mm),
            (0, tag_size_mm),
        ],
        close=True,
        dxfattribs={"layer": "TAG"}
    )

    # --------------------------------------------------------
    # 흰색 여백(Quiet Zone) 가이드
    # --------------------------------------------------------
    if DRAW_GUIDE:

        q = quiet_mm

        msp.add_lwpolyline(
            [
                (-q, -q),
                (tag_size_mm + q, -q),
                (tag_size_mm + q, tag_size_mm + q),
                (-q, tag_size_mm + q),
            ],
            close=True,
            dxfattribs={
                "layer": "GUIDE",
                "linetype": "DASHED",
                "ltscale": max(module_size / 2, 0.1),
            }
        )

        # 안내 문구 (가이드 사각형 바로 아래)
        text_height = max(module_size * 0.4, 0.5)

        text = msp.add_text(
            f"KEEP WHITE: {QUIET_ZONE_MODULES:g} module = {quiet_mm:.2f}mm",
            height=text_height,
            dxfattribs={"layer": "GUIDE"}
        )

        text.set_placement(
            (-q, -q - text_height * 1.8)
        )

    # 파일 저장
    doc.saveas(
        filepath
    )


# ============================================================
# 태그 6개 생성
# ============================================================

print()
print("=" * 60)
print("AprilTag 생성")
print("=" * 60)

print()
print(f"태그 실제 크기 : {tag_size_mm} mm")
print(f"1 module       : {module_mm:.3f} mm")
print(f"흰색 여백      : {QUIET_ZONE_MODULES:g} module = {quiet_mm:.3f} mm (사방)")
print(f"가이드라인     : {'표시' if DRAW_GUIDE else '없음'}")
print(f"PNG 해상도    : {DPI} DPI")
print(f"태그 픽셀      : {tag_pixels} x {tag_pixels}")
print(f"PNG 전체       : {image_pixels} x {image_pixels} px"
      f" ({image_mm:.2f} x {image_mm:.2f} mm)")
print(f"AprilTag       : 36h11")
print()


generated_images = []


for tag_id, position_name in TAGS.items():

    # --------------------------------------------------------
    # 이미지 생성 (흰색 여백 + 가이드 포함)
    # --------------------------------------------------------

    tag_image = create_tag_image(
        tag_id
    )

    image = create_tag_with_guide(
        tag_image
    )

    # --------------------------------------------------------
    # PNG
    # --------------------------------------------------------

    png_filename = (
        f"ID_{tag_id}_{position_name}.png"
    )

    png_path = (
        output_dir
        / png_filename
    )

    save_png(
        image,
        png_path
    )

    # --------------------------------------------------------
    # DXF
    # --------------------------------------------------------

    dxf_filename = (
        f"ID_{tag_id}_{position_name}.dxf"
    )

    dxf_path = (
        output_dir
        / dxf_filename
    )

    create_dxf(
        tag_id,
        dxf_path
    )

    # 저장
    generated_images.append(
        (
            tag_id,
            position_name,
            image
        )
    )

    print(
        f"ID {tag_id} 생성 완료"
    )
    print(
        f"  PNG : {png_path.name}"
    )
    print(
        f"  DXF : {dxf_path.name}"
    )
    print()


# ============================================================
# 6개 태그 전체 이미지 생성
# ============================================================

margin = int(
    round(20 * pixels_per_mm)
)

label_height = int(
    round(15 * pixels_per_mm)
)

cell_width = image_pixels

cell_height = (
    image_pixels
    + label_height
)

sheet_width = (
    cell_width * 2
    + margin * 3
)

sheet_height = (
    cell_height * 3
    + margin * 4
)


sheet = np.full(
    (
        sheet_height,
        sheet_width,
        3
    ),
    255,
    dtype=np.uint8
)


# ============================================================
# 6개 배치
# ============================================================

for index, (
    tag_id,
    position_name,
    image
) in enumerate(generated_images):

    row = index % 3
    col = index // 3

    x = (
        margin
        + col * (cell_width + margin)
    )

    y = (
        margin
        + row * (cell_height + margin)
    )

    # 태그 (여백 + 가이드 포함)
    sheet[
        y:y + image_pixels,
        x:x + image_pixels
    ] = image

    # 글자
    label = (
        f"ID {tag_id} - "
        f"{position_name}"
    )

    cv2.putText(
        sheet,
        label,
        (
            x,
            y + image_pixels + int(
                label_height * 0.7
            )
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
        cv2.LINE_AA
    )


# ============================================================
# 전체 이미지 저장
# ============================================================

sheet_path = (
    output_dir
    / "AprilTag_6개_전체.png"
)

save_png(
    sheet,
    sheet_path
)


# ============================================================
# 완료
# ============================================================

print("=" * 60)
print("생성 완료!")
print("=" * 60)

print()
print(f"저장 폴더:")
print(output_dir)

print()
print("태그 크기:")
print(f"{tag_size_mm} mm x {tag_size_mm} mm")

print()
print("흰색 여백 (태그 사방):")
print(f"{quiet_mm:.3f} mm ({QUIET_ZONE_MODULES:g} module)")

print()
print("태그 목록:")

for tag_id, position_name in TAGS.items():

    print(
        f"  ID {tag_id} : {position_name}"
    )

print()
print("전체 이미지:")
print(sheet_path)

print()
