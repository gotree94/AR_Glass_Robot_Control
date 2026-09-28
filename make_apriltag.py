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
# 출력 이미지 자체의 해상도
TAG_SIZE = 1000

# 태그 주변 흰색 여백
BORDER_SIZE = 150

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
# 태그 생성 함수
# ============================================================

def create_apriltag(tag_id, position_name):

    # 전체 캔버스
    canvas_size = TAG_SIZE + BORDER_SIZE * 2

    canvas = np.ones(
        (canvas_size, canvas_size),
        dtype=np.uint8
    ) * 255

    # AprilTag 생성
    tag_image = cv2.aruco.generateImageMarker(
        aruco_dict,
        tag_id,
        TAG_SIZE
    )

    # 중앙에 배치
    x = BORDER_SIZE
    y = BORDER_SIZE

    canvas[
        y:y + TAG_SIZE,
        x:x + TAG_SIZE
    ] = tag_image

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

cell_width = TAG_SIZE + BORDER_SIZE * 2
cell_height = TAG_SIZE + BORDER_SIZE * 2 + label_height

sheet_width = cell_width * 2 + margin * 3
sheet_height = cell_height * 3 + margin * 4

sheet = np.ones(
    (sheet_height, sheet_width),
    dtype=np.uint8
) * 255


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
        0,
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
print("생성된 태그:")
print()

for tag_id, position_name in TAGS.items():
    print(f"ID {tag_id}: {position_name}")

print()
print(f"전체 출력 파일:")
print(sheet_path)
print()
