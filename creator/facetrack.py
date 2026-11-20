"""Face tracking for Shorts.

Two jobs:
  1. find_facecam(): find where your facecam sits in a gameplay stream. A face that shows up in
     the same place across the whole stream is your camera; NPC faces in the game move around,
     so they are ignored. Used by --facecam auto.
  2. track_crop():  for full-screen camera footage, make the 9:16 crop follow your face smoothly.
     Used by --shorts-style track.

Needs: pip install "opencv-python-headless<5" (OpenCV 4 includes the face detector, no download).

Check what it finds:
    python creator/facetrack.py stream.mp4
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path


def _cv():
    try:
        import cv2
    except ImportError:
        sys.exit('Face tracking needs OpenCV. Run: pip install "opencv-python-headless<5"')
    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if not hasattr(cv2, "CascadeClassifier") or not Path(path).exists():
        sys.exit('This OpenCV has no built-in face detector. Run: pip install "opencv-python-headless<5"')
    return cv2, cv2.CascadeClassifier(path)


def sample_faces(src: Path, times: list[float], bars: tuple | None = None) -> list[tuple[float, list]]:
    """Faces at each time, as (x, y, w, h) fractions of the (bar-cropped) frame."""
    cv2, det = _cv()
    cap = cv2.VideoCapture(str(src))
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        if bars:
            w, h, x, y = bars
            frame = frame[y:y + h, x:x + w]
        H, W = frame.shape[:2]
        scale = 640 / W
        small = cv2.resize(frame, (640, max(2, int(H * scale))))
        gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
        faces = det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(24, 24))
        sh, sw = gray.shape
        out.append((t, [(fx / sw, fy / sh, fw / sw, fh / sh) for fx, fy, fw, fh in faces]))
    cap.release()
    return out


def find_facecam(src: Path, total: float, bars: tuple | None = None, samples: int = 40,
                 min_share: float = 0.3) -> tuple | None:
    """Returns the facecam box as (x, y, w, h) in percent of the frame, or None."""
    step = total / (samples + 1)
    hits = sample_faces(src, [step * (i + 1) for i in range(samples)], bars)
    faces = [f for _, fs in hits for f in fs]
    if not hits or not faces:
        return None
    # Group face centres into a 10x10 grid; the busiest cell is the camera.
    cells: dict[tuple, list] = {}
    for f in faces:
        cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
        cells.setdefault((int(cx * 10), int(cy * 10)), []).append(f)
    best = max(cells.values(), key=len)
    frames_with = sum(1 for _, fs in hits if any(f in best for f in fs))
    if frames_with < min_share * len(hits):
        return None
    cx = statistics.median(f[0] + f[2] / 2 for f in best)
    cy = statistics.median(f[1] + f[3] / 2 for f in best)
    fw = statistics.median(f[2] for f in best)
    # Box around the face: ~3 face-widths wide, 4:3 on a 16:9 frame, clamped inside the frame.
    w = min(1.0, fw * 3.0)
    h = min(1.0, w * (16 / 9) * (3 / 4))
    x = min(max(0.0, cx - w / 2), 1 - w)
    y = min(max(0.0, cy - h * 0.45), 1 - h)
    return tuple(round(float(v) * 100, 2) for v in (x, y, w, h))


def track_crop(src: Path, start: float, dur: float, frame_w: int, frame_h: int,
               bars: tuple | None = None, step: float = 0.5) -> tuple[int, list[tuple[float, int]]] | None:
    """Crop width and a smoothed list of (time in clip, crop x) that keeps the face centred."""
    crop_w = min(frame_w, int(frame_h * 9 / 16) // 2 * 2)
    n = max(2, int(dur / step) + 1)
    hits = sample_faces(src, [start + i * step for i in range(n)], bars)
    centres = []
    last = None
    for t, fs in hits:
        if fs:
            big = max(fs, key=lambda f: f[2] * f[3])  # follow the largest face
            last = (big[0] + big[2] / 2) * frame_w
        centres.append((t - start, last))
    if all(c is None for _, c in centres):
        return None
    first = next(c for _, c in centres if c is not None)
    xs, prev = [], first
    for t, c in centres:
        c = prev if c is None else c
        prev = 0.75 * prev + 0.25 * c  # smooth so the camera doesn't jitter
        x = int(min(max(0, prev - crop_w / 2), frame_w - crop_w)) // 2 * 2
        xs.append((round(t, 2), x))
    return crop_w, xs


def write_sendcmd(path: Path, points: list[tuple[float, int]], target: str = "crop@track") -> Path:
    lines = [f"{t:.2f} {target} x {x};" for t, x in points]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Find the facecam in a recording.")
    ap.add_argument("video", type=Path)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from find_moments import duration
    box = find_facecam(a.video, duration(a.video))
    if box:
        print(f"Facecam found at x={box[0]}% y={box[1]}% w={box[2]}% h={box[3]}%")
        print(f"Use: --facecam auto   (or --facecam {','.join(str(v) for v in box)})")
    else:
        print("No steady facecam found. Shorts will use the normal layout.")


if __name__ == "__main__":
    main()
