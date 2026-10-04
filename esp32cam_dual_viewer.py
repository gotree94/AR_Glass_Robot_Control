#!/usr/bin/env python3
"""
ESP32-CAM 2대 MJPEG 스트림을 하나의 Tkinter UI에 표시

설치:  pip install requests pillow
실행:  python esp32cam_dual_viewer.py

- 스트림 주소: http://<IP>:81/stream  (CameraWebServer 기본)
- 카메라마다 별도 스레드로 수신, 끊기면 자동 재연결
- 's' 키 또는 [스냅샷 저장] 버튼: 현재 프레임을 snapshots/ 폴더에 저장
"""

import io
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import requests
from PIL import Image, ImageTk

# ------------------------------------------------------------------ 설정
CAMERAS = [
    # rotate: 시계 방향이 +, 반시계 방향이 - (단위: 도, 90 단위만 지원)
    {"name": "CAM 2", "host": "192.168.1.7", "rotate": -90},   # 왼쪽
    {"name": "CAM 1", "host": "192.168.1.5", "rotate": 90},    # 오른쪽
]
STREAM_PORT = 81
STREAM_PATH = "/stream"
DISPLAY_SIZE = (480, 640)      # 카메라당 표시 영역 (가로, 세로) - 90도 회전하면 세로가 길어짐
UI_REFRESH_MS = 30             # UI 갱신 주기
STALE_SEC = 3.0                # 이 시간 동안 프레임 없으면 '끊김' 표시
SNAPSHOT_DIR = "snapshots"
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
        root.title("ESP32-CAM Dual Viewer")
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Key-s>", lambda e: self.save_snapshots())
        root.bind("<Escape>", lambda e: self.on_close())

        self.workers = [CamWorker(c["name"], c["host"]) for c in CAMERAS]
        self.labels, self.info_vars, self.photos = [], [], [None] * len(CAMERAS)

        frame = ttk.Frame(root, padding=6)
        frame.pack(fill="both", expand=True)

        for i, c in enumerate(CAMERAS):
            box = ttk.LabelFrame(frame, text=f"{c['name']}  ({c['host']})")
            box.grid(row=0, column=i, padx=4, pady=4)
            lbl = tk.Label(box, width=DISPLAY_SIZE[0], height=DISPLAY_SIZE[1],
                           bg="black", fg="white", text="대기 중",
                           compound="center")
            # Label의 width/height는 이미지가 없을 때 '문자 단위'이므로 픽셀 지정용 빈 이미지 사용
            blank = ImageTk.PhotoImage(Image.new("RGB", DISPLAY_SIZE, "black"))
            lbl.configure(image=blank, width=DISPLAY_SIZE[0], height=DISPLAY_SIZE[1])
            lbl.image = blank
            lbl.pack()
            var = tk.StringVar(value="-")
            ttk.Label(box, textvariable=var).pack(anchor="w", padx=4, pady=2)
            self.labels.append(lbl)
            self.info_vars.append(var)

        bar = ttk.Frame(frame)
        bar.grid(row=1, column=0, columnspan=len(CAMERAS), sticky="ew", pady=4)
        ttk.Button(bar, text="스냅샷 저장 (s)", command=self.save_snapshots).pack(side="left")
        ttk.Button(bar, text="종료 (Esc)", command=self.on_close).pack(side="right")

        for w in self.workers:
            w.start()
        self.update_ui()

    def update_ui(self):
        now = time.time()
        for i, w in enumerate(self.workers):
            img, ts, fps = w.get_frame()
            alive = img is not None and (now - ts) < STALE_SEC
            if alive:
                rot = rotate_img(img.convert("RGB"), CAMERAS[i].get("rotate", 0))
                disp = fit_to_box(rot, DISPLAY_SIZE)
                self.photos[i] = ImageTk.PhotoImage(disp)
                self.labels[i].configure(image=self.photos[i])
                self.labels[i].image = self.photos[i]
                self.info_vars[i].set(f"{w.status} | {img.size[0]}x{img.size[1]} | {fps:.1f} FPS")
            else:
                self.info_vars[i].set(f"끊김 - {w.status}")
        self.root.after(UI_REFRESH_MS, self.update_ui)

    def save_snapshots(self):
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for c, w in zip(CAMERAS, self.workers):
            img, _, _ = w.get_frame()
            if img is not None:
                path = os.path.join(SNAPSHOT_DIR, f"{c['name'].replace(' ', '')}_{stamp}.jpg")
                rotate_img(img.convert("RGB"), c.get("rotate", 0)).save(path, quality=95)
                print("saved:", path)

    def on_close(self):
        for w in self.workers:
            w.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
