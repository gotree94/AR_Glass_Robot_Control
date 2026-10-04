#!/usr/bin/env python3
"""
ESP32-CAM 2대 MJPEG 스트림을 하나의 Tkinter UI에 표시 + AprilTag(36h11) 인식

설치:  pip install requests pillow numpy "opencv-python>=4.7"
실행:  python esp32cam_dual_viewer.py

- 스트림 주소: http://<IP>:81/stream  (CameraWebServer 기본)
- 카메라마다 별도 스레드로 수신, 끊기면 자동 재연결
- AprilTag 36h11, ID 0~5, 실제 크기 68mm (검은 테두리 바깥쪽 기준)
- 's' 키 또는 [스냅샷 저장] 버튼: 회전 적용된 원본 프레임을 snapshots/ 에 저장
"""

import io
import math
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import cv2
import numpy as np
import requests
from PIL import Image, ImageTk

# ------------------------------------------------------------------ 설정
CAMERAS = [
    # rotate: 시계 방향이 +, 반시계 방향이 - (단위: 도, 90 단위만 지원)
    # fov   : 회전 전 원본 영상의 '가로' 화각(도). 거리 계산용 추정값 (아래 설명 참고)
    {"name": "CAM 2", "host": "192.168.1.7", "rotate": -90, "fov": 65.0},   # 왼쪽
    {"name": "CAM 1", "host": "192.168.1.5", "rotate": 90,  "fov": 65.0},   # 오른쪽
]
STREAM_PORT = 81
STREAM_PATH = "/stream"
DISPLAY_SIZE = (480, 640)      # 카메라당 표시 영역 (가로, 세로)
UI_REFRESH_MS = 30             # UI 갱신 주기
STALE_SEC = 3.0                # 이 시간 동안 프레임 없으면 '끊김' 표시
SNAPSHOT_DIR = "snapshots"

# --- AprilTag 설정
TAG_DICT = cv2.aruco.DICT_APRILTAG_36h11
TAG_SIZE_MM = 68.0             # 검은 테두리 바깥 한 변의 실제 길이
TAG_NAMES = {
    0: "RIGHT_1_THUMB_INDEX",
    1: "RIGHT_2_HAND",
    2: "RIGHT_3_FOREARM",
    3: "LEFT_1_THUMB_INDEX",
    4: "LEFT_2_HAND",
    5: "LEFT_3_FOREARM",
}
# ----------------------------------------------------------------------


def rotate_img(img, deg):
    """시계 방향 +deg 회전 (PIL의 rotate는 반시계가 +이므로 부호 반전)"""
    deg %= 360
    if deg == 0:
        return img
    return img.rotate(-deg, expand=True)


def fit_to_box(img, size):
    """비율을 유지한 채 size 안에 맞추고 나머지는 검은색으로 채움"""
    scale = min(size[0] / img.width, size[1] / img.height)
    new_w, new_h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    img = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", size, "black")
    canvas.paste(img, ((size[0] - new_w) // 2, (size[1] - new_h) // 2))
    return canvas


class TagDetector:
    """AprilTag 36h11 검출 + 68mm 기준 자세(위치) 추정 + 화면 표시"""

    def __init__(self):
        dictionary = cv2.aruco.getPredefinedDictionary(TAG_DICT)
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(dictionary, params)
        h = TAG_SIZE_MM / 2.0
        # 코너 순서: 좌상, 우상, 우하, 좌하 (태그 중심이 원점, 단위 mm)
        self.obj_pts = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]],
                                dtype=np.float64)

    def process(self, rgb, focal_px):
        """rgb(ndarray)에 검출 결과를 직접 그리고, 검출 리스트를 반환"""
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        results = []
        if ids is None:
            return results

        hgt, wid = gray.shape
        K = np.array([[focal_px, 0, wid / 2.0],
                      [0, focal_px, hgt / 2.0],
                      [0, 0, 1]], dtype=np.float64)
        dist = np.zeros(5)

        for c, tag_id in zip(corners, ids.flatten()):
            tag_id = int(tag_id)
            if tag_id not in TAG_NAMES:      # ID 0~5 외에는 무시
                continue
            pts = c.reshape(4, 2).astype(np.float64)
            ok, rvec, tvec = cv2.solvePnP(self.obj_pts, pts, K, dist,
                                          flags=cv2.SOLVEPNP_IPPE_SQUARE)
            if not ok:
                continue
            x, y, z = tvec.flatten()
            d = float(np.linalg.norm(tvec))
            results.append({"id": tag_id, "name": TAG_NAMES[tag_id],
                            "x": x, "y": y, "z": z, "dist": d})

            # ---- 그리기
            poly = pts.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(rgb, [poly], True, (0, 255, 0), 2)
            cv2.circle(rgb, tuple(poly[0, 0]), 5, (255, 0, 0), -1)   # 좌상단 코너 표시
            cv2.drawFrameAxes(rgb, K, dist, rvec, tvec, TAG_SIZE_MM * 0.6, 2)
            label = f"ID{tag_id} {d:.0f}mm"
            org = (int(pts[:, 0].min()), max(15, int(pts[:, 1].min()) - 8))
            cv2.putText(rgb, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(rgb, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1, cv2.LINE_AA)

        results.sort(key=lambda r: r["id"])
        return results


class CamWorker(threading.Thread):
    """MJPEG 스트림을 받아 최신 프레임(PIL.Image)만 보관하는 스레드"""

    def __init__(self, name, host):
        super().__init__(daemon=True)
        self.name = name
        self.url = f"http://{host}:{STREAM_PORT}{STREAM_PATH}"
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._frame = None
        self._frame_time = 0.0
        self._fps = 0.0
        self.status = "연결 중..."

    # ---- 외부에서 호출
    def get_frame(self):
        with self._lock:
            return self._frame, self._frame_time, self._fps

    def stop(self):
        self._stop_evt.set()

    # ---- 스레드 본체
    def run(self):
        while not self._stop_evt.is_set():
            try:
                self.status = "연결 중..."
                with requests.get(self.url, stream=True, timeout=(3, 5)) as resp:
                    resp.raise_for_status()
                    self.status = "수신 중"
                    self._read_mjpeg(resp)
            except Exception as e:  # 네트워크 오류 등
                self.status = f"오류: {type(e).__name__}"
            # 재연결 전 잠깐 대기
            self._stop_evt.wait(1.5)

    def _read_mjpeg(self, resp):
        buf = b""
        t0, n = time.time(), 0
        for chunk in resp.iter_content(chunk_size=1024):
            if self._stop_evt.is_set():
                return
            if not chunk:
                continue
            buf += chunk
            while True:
                soi = buf.find(b"\xff\xd8")          # JPEG 시작
                if soi == -1:
                    buf = buf[-1:]
                    break
                eoi = buf.find(b"\xff\xd9", soi + 2)  # JPEG 끝
                if eoi == -1:
                    buf = buf[soi:]
                    break
                jpg, buf = buf[soi:eoi + 2], buf[eoi + 2:]
                try:
                    img = Image.open(io.BytesIO(jpg))
                    img.load()
                except Exception:
                    continue  # 깨진 프레임은 버림
                n += 1
                now = time.time()
                with self._lock:
                    self._frame = img
                    self._frame_time = now
                    if now - t0 >= 1.0:
                        self._fps = n / (now - t0)
                        t0, n = now, 0


class App:
    def __init__(self, root):
        self.root = root
        root.title("ESP32-CAM Dual Viewer + AprilTag")
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Key-s>", lambda e: self.save_snapshots())
        root.bind("<Escape>", lambda e: self.on_close())

        n = len(CAMERAS)
        self.detector = TagDetector()
        self.workers = [CamWorker(c["name"], c["host"]) for c in CAMERAS]
        self.labels, self.info_vars, self.tag_vars = [], [], []
        self.photos = [None] * n
        self.raw_rot = [None] * n      # 스냅샷용 (회전만 적용, 표시 없음)
        self.last_ts = [0.0] * n
        self.detect_on = tk.BooleanVar(value=True)

        frame = ttk.Frame(root, padding=6)
        frame.pack(fill="both", expand=True)

        for i, c in enumerate(CAMERAS):
            box = ttk.LabelFrame(frame, text=f"{c['name']}  ({c['host']})")
            box.grid(row=0, column=i, padx=4, pady=4)
            blank = ImageTk.PhotoImage(Image.new("RGB", DISPLAY_SIZE, "black"))
            lbl = tk.Label(box, image=blank, bg="black")
            lbl.image = blank
            lbl.pack()
            info = tk.StringVar(value="-")
            ttk.Label(box, textvariable=info).pack(anchor="w", padx=4, pady=(2, 0))
            tags = tk.StringVar(value="")
            tk.Label(box, textvariable=tags, font=("Consolas", 9), justify="left",
                     anchor="nw", height=6, width=62).pack(anchor="w", padx=4, pady=(0, 2))
            self.labels.append(lbl)
            self.info_vars.append(info)
            self.tag_vars.append(tags)

        bar = ttk.Frame(frame)
        bar.grid(row=1, column=0, columnspan=n, sticky="ew", pady=4)
        ttk.Button(bar, text="스냅샷 저장 (s)", command=self.save_snapshots).pack(side="left")
        ttk.Checkbutton(bar, text="AprilTag 인식", variable=self.detect_on).pack(side="left", padx=12)
        ttk.Button(bar, text="종료 (Esc)", command=self.on_close).pack(side="right")

        for w in self.workers:
            w.start()
        self.update_ui()

    def process_frame(self, i, img):
        """새 프레임 1장 처리: 회전 -> 태그 인식 -> 표시용 이미지 반환"""
        cam = CAMERAS[i]
        fov = cam.get("fov", 65.0)
        # 초점거리(px): 원본 가로 화각 기준. 회전해도 초점거리는 변하지 않음
        focal = (img.width / 2.0) / math.tan(math.radians(fov) / 2.0)

        raw = rotate_img(img.convert("RGB"), cam.get("rotate", 0))
        self.raw_rot[i] = raw
        arr = np.array(raw)                       # 복사본 (여기에만 그림)
        tags = self.detector.process(arr, focal) if self.detect_on.get() else []

        lines = [f"ID{t['id']} {t['name']:<19} {t['dist']:6.0f}mm  "
                 f"xyz=({t['x']:.0f},{t['y']:.0f},{t['z']:.0f})" for t in tags]
        self.tag_vars[i].set("\n".join(lines))
        return fit_to_box(Image.fromarray(arr), DISPLAY_SIZE), len(tags)

    def update_ui(self):
        now = time.time()
        for i, w in enumerate(self.workers):
            img, ts, fps = w.get_frame()
            alive = img is not None and (now - ts) < STALE_SEC
            if not alive:
                self.info_vars[i].set(f"끊김 - {w.status}")
                self.tag_vars[i].set("")
                continue
            if ts != self.last_ts[i]:             # 새 프레임일 때만 처리
                self.last_ts[i] = ts
                disp, n_tags = self.process_frame(i, img)
                self.photos[i] = ImageTk.PhotoImage(disp)
                self.labels[i].configure(image=self.photos[i])
                self.labels[i].image = self.photos[i]
                self.info_vars[i].set(
                    f"{w.status} | {img.size[0]}x{img.size[1]} | {fps:.1f} FPS | 태그 {n_tags}개")
        self.root.after(UI_REFRESH_MS, self.update_ui)

    def save_snapshots(self):
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for c, raw in zip(CAMERAS, self.raw_rot):
            if raw is not None:
                path = os.path.join(SNAPSHOT_DIR, f"{c['name'].replace(' ', '')}_{stamp}.jpg")
                raw.save(path, quality=95)
                print("saved:", path)

    def on_close(self):
        for w in self.workers:
            w.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
