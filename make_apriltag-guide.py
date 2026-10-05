import cv2
import os
import numpy as np
from pathlib import Path


# ============================================================
# 설정
# ============================================================

# AprilTag 종류
# ESP32-CAM + OpenCV에서 사용하기 좋은 36h11
TAG_FAMILY = cv2.aruco.DICT_APRILTAG_36h11

# 생성할 태그 크기 (픽셀)
# 검은 테두리를 포함한 태그 본체 크기 (8 x 8 module)
TAG_SIZE = 1000

# AprilTag 36h11 : 검은 테두리 포함 8 x 8 module
TAG_GRID = 8

# ------------------------------------------------------------
# 흰색 여백(Quiet Zone) 설정
# ------------------------------------------------------------
# 태그 바깥쪽에 반드시 비워둬야 하는 흰색 영역의 폭 (module 단위)
#   1.0 = 최소값 (이보다 작으면 인식률 급락)
#   1.5 ~ 2.0 = 권장 (ESP32-CAM처럼 해상도가 낮거나 비스듬히 볼 때)
QUIET_ZONE_MODULES = 1.0

# 가이드라인 표시 여부 (False 면 가이드 없이 흰 여백만 생성)
DRAW_GUIDE = True

# 가이드라인 바깥쪽 추가 여백 (px) - 선과 문구가 들어갈 공간
GUIDE_PAD = 60

# 가이드라인 색상 (B, G, R)
GUIDE_COLOR = (0, 0, 255)       # 빨강

# 태그 ID와 위치
TAGS = {
    0: "RIGHT_1_THUMB_INDEX",       # 오른쪽 엄지/검지
    1: "RIGHT_2_HAND",              # 오른쪽 손등/엄지 측면
    2: "RIGHT_3_FOREARM",           # 오른쪽 하박
    3: "LEFT_1_THUMB_INDEX",        # 왼쪽 엄지/검지
    4: "LEFT_2_HAND",               # 왼쪽 손등/엄지 측면
    5: "LEFT_3_FOREARM",            # 왼쪽 하박
}


# ============================================================
# 파생 값 계산
# ============================================================

MODULE_PX = TAG_SIZE / TAG_GRID
QUIET_PX = int(round(MODULE_PX * QUIET_ZONE_MODULES))
PAD_PX = GUIDE_PAD if DRAW_GUIDE else 0

# 개별 태그 이미지 한 장의 전체 크기 (정사각형)
IMAGE_SIZE = TAG_SIZE + (QUIET_PX + PAD_PX) * 2


# ============================================================
# 바탕화면 경로 찾기
# ============================================================

desktop = Path.home() / "Desktop"

# 한글 Windows에서 Desktop 폴더 이름이 다를 경우를 대비
if not desktop.exists():
    desktop = Path.home() / "바탕 화면"

if not desktop.exists():
    print("바탕화면 폴더를 찾을 수 없습니다.")
    print("현재 사용자 폴더에 저장합니다.")
    desktop = Path.home()


# ============================================================
# 출력 폴더 생성
# ============================================================

output_dir = desktop / "AprilTag_6개"
output_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# AprilTag dictionary 생성
# ============================================================

aruco_dict = cv2.aruco.getPredefinedDictionary(TAG_FAMILY)


# ============================================================
# 가이드라인 그리기 도구
# ============================================================

def draw_dashed_line(img, p1, p2, color, thickness=3, dash=24, gap=14):
    """두 점 사이에 점선을 그립니다."""

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


def draw_dashed_rect(img, top_left, bottom_right, color, thickness=3):
    """점선 사각형"""

    x1, y1 = top_left
    x2, y2 = bottom_right

    draw_dashed_line(img, (x1, y1), (x2, y1), color, thickness)
    draw_dashed_line(img, (x2, y1), (x2, y2), color, thickness)
    draw_dashed_line(img, (x2, y2), (x1, y2), color, thickness)
    draw_dashed_line(img, (x1, y2), (x1, y1), color, thickness)


def draw_corner_marks(img, top_left, bottom_right, color,
                      length=40, thickness=4):
    """네 모서리에 실선 'ㄱ'자 표시 (자를 때 기준선)"""

    x1, y1 = top_left
    x2, y2 = bottom_right

    # 좌상
    cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness, cv2.LINE_AA)

    # 우상
    cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness, cv2.LINE_AA)

    # 좌하
    cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness, cv2.LINE_AA)

    # 우하
    cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness, cv2.LINE_AA)


def fit_text(img, text, org_x, baseline_y, max_width, color,
             max_scale=0.7, thickness=1):
    """폭에 맞춰 글자 크기를 줄여가며 텍스트를 넣습니다."""

    scale = max_scale

    while scale > 0.25:

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
# 태그 생성 함수
# ============================================================

def create_apriltag(tag_id, position_name):

    # 전체 캔버스 (흰색, 컬러)
    canvas = np.full(
        (IMAGE_SIZE, IMAGE_SIZE, 3),
        255,
        dtype=np.uint8
    )

    # AprilTag 생성 (흑백)
    tag_image = cv2.aruco.generateImageMarker(
        aruco_dict,
        tag_id,
        TAG_SIZE
    )

    # 중앙에 배치 : [가이드 여백][Quiet Zone][태그]
    offset = QUIET_PX + PAD_PX

    canvas[
        offset:offset + TAG_SIZE,
        offset:offset + TAG_SIZE
    ] = cv2.cvtColor(tag_image, cv2.COLOR_GRAY2BGR)

    # --------------------------------------------------------
    # 가이드라인
    # --------------------------------------------------------
    if DRAW_GUIDE:

        g1 = PAD_PX
        g2 = IMAGE_SIZE - PAD_PX - 1

        # 흰색 영역의 바깥 경계 (점선)
        draw_dashed_rect(
            canvas,
            (g1, g1),
            (g2, g2),
            GUIDE_COLOR
        )

        # 모서리 표시
        draw_corner_marks(
            canvas,
            (g1, g1),
            (g2, g2),
            GUIDE_COLOR
        )

        # 안내 문구 (선 바깥, 위쪽 여백)
        note = (
            f"KEEP WHITE INSIDE LINE: "
            f"{QUIET_ZONE_MODULES:g} module = {QUIET_PX}px"
        )

        fit_text(
            canvas,
            note,
            g1,
            max(PAD_PX - 18, 20),
            g2 - g1,
            GUIDE_COLOR
        )

    # 파일명
    filename = f"ID_{tag_id}_{position_name}.png"

    filepath = output_dir / filename

    # 저장
    cv2.imwrite(
        str(filepath),
        canvas
    )

    print(f"생성 완료: {filepath}")

    return canvas


# ============================================================
# 개별 태그 6개 생성
# ============================================================

generated_images = []

for tag_id, position_name in TAGS.items():

    image = create_apriltag(
        tag_id,
        position_name
    )

    generated_images.append(
        (tag_id, position_name, image)
    )


# ============================================================
# 6개 태그를 한 장에 배치한 출력물 생성
# ============================================================

margin = 100
label_height = 100

cell_width = IMAGE_SIZE
cell_height = IMAGE_SIZE + label_height

sheet_width = cell_width * 2 + margin * 3
sheet_height = cell_height * 3 + margin * 4

sheet = np.full(
    (sheet_height, sheet_width, 3),
    255,
    dtype=np.uint8
)


# 태그 배치
for index, (tag_id, position_name, image) in enumerate(generated_images):

    row = index % 3
    col = index // 3

    x = margin + col * (cell_width + margin)
    y = margin + row * (cell_height + margin)

    # 태그 이미지
    sheet[
        y:y + image.shape[0],
        x:x + image.shape[1]
    ] = image

    # 설명
    label = f"ID {tag_id} - {position_name}"

    cv2.putText(
        sheet,
        label,
        (x, y + image.shape[0] + 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
        cv2.LINE_AA
    )


# 한 장짜리 출력 파일
sheet_path = output_dir / "AprilTag_6개_전체.png"

cv2.imwrite(
    str(sheet_path),
    sheet
)


# ============================================================
# 결과
# ============================================================

print()
print("=" * 60)
print("AprilTag 생성이 완료되었습니다.")
print("=" * 60)
print()
print(f"저장 위치:")
print(output_dir)
print()
print(f"태그 본체      : {TAG_SIZE} x {TAG_SIZE} px ({TAG_GRID} x {TAG_GRID} module)")
print(f"1 module       : {MODULE_PX:g} px")
print(f"흰색 여백      : {QUIET_ZONE_MODULES:g} module = {QUIET_PX} px (사방)")
print(f"가이드라인     : {'표시' if DRAW_GUIDE else '없음'}")
print(f"이미지 전체    : {IMAGE_SIZE} x {IMAGE_SIZE} px")
print()
print("생성된 태그:")
print()

for tag_id, position_name in TAGS.items():
    print(f"ID {tag_id}: {position_name}")

print()
print(f"전체 출력 파일:")
print(sheet_path)
print()
