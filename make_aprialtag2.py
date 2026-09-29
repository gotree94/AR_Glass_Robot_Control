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
# PNG 해상도 계산
# ============================================================

# 실제 mm → 600 DPI 픽셀
pixels_per_mm = DPI / 25.4

tag_pixels = int(
    round(tag_size_mm * pixels_per_mm)
)


# 너무 작은 이미지 방지
tag_pixels = max(tag_pixels, 100)


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
# PNG 저장
# ============================================================

def save_png(image, filepath):

    # OpenCV grayscale → PIL
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

    전체 태그 크기:
        tag_size_mm x tag_size_mm

    AprilTag 36h11:
        8 x 8 module
    """

    doc = ezdxf.new(
        "R2010"
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
                    close=True
                )

    # 외곽선
    msp.add_lwpolyline(
        [
            (0, 0),
            (tag_size_mm, 0),
            (tag_size_mm, tag_size_mm),
            (0, tag_size_mm),
        ],
        close=True
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
print(f"PNG 해상도    : {DPI} DPI")
print(f"PNG 픽셀      : {tag_pixels} x {tag_pixels}")
print(f"AprilTag       : 36h11")
print()


generated_images = []


for tag_id, position_name in TAGS.items():

    # --------------------------------------------------------
    # 이미지 생성
    # --------------------------------------------------------

    image = create_tag_image(
        tag_id
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

cell_width = tag_pixels

cell_height = (
    tag_pixels
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


sheet = np.ones(
    (
        sheet_height,
        sheet_width
    ),
    dtype=np.uint8
) * 255


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

    # 태그
    sheet[
        y:y + tag_pixels,
        x:x + tag_pixels
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
            y + tag_pixels + int(
                label_height * 0.7
            )
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        0,
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
print("태그 목록:")

for tag_id, position_name in TAGS.items():

    print(
        f"  ID {tag_id} : {position_name}"
    )

print()
print("전체 이미지:")
print(sheet_path)

print()
