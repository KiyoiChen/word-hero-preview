import math
import subprocess
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# v4: use a REAL open-mouth reference and deform only the lower jaw.
# This avoids the old "draw a black oval" approach that visibly drifted off the face.

MASTER = Path("assets/cat_master.png")
AUDIO = Path("voice.wav")
OUTDIR = Path("output")
FPS_MOUTH = 8

# Tuned for the current prototype crop (941x600).
# If the master image changes, retune this ROI after visually checking a zoomed mouth crop.
ROI = (500, 340, 720, 520)  # x0, y0, x1, y1
MOUTH_CX = 110.0            # relative to ROI
MOUTH_Y = 82.0              # relative to ROI

OUTDIR.mkdir(exist_ok=True)


def make_mouth_state(image: np.ndarray, close_amount: float) -> np.ndarray:
    """0.0 = original open mouth, 1.0 = most-closed state."""
    if close_amount <= 0:
        return image.copy()

    x0, y0, x1, y1 = ROI
    out = image.copy()
    roi = image[y0:y1, x0:x1].copy()
    rh, rw = roi.shape[:2]

    yy, xx = np.mgrid[0:rh, 0:rw].astype(np.float32)

    # Pull the lower lip/chin upward into the natural mouth opening.
    # No synthetic dark ellipse is painted.
    vertical = np.exp(-((yy - (MOUTH_Y + 18.0)) / 48.0) ** 2)
    horizontal = np.exp(-((xx - MOUTH_CX) / 88.0) ** 4)
    shift = close_amount * 30.0 * vertical * horizontal

    warped = cv2.remap(
        roi,
        xx,
        np.clip(yy + shift, 0, rh - 1),
        cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT,
    )

    # Feather deformation into the surrounding muzzle/fur.
    mask = np.exp(
        -(
            ((xx - MOUTH_CX) / 100.0) ** 4
            + ((yy - (MOUTH_Y + 15.0)) / 85.0) ** 4
        )
    )[..., None]

    out[y0:y1, x0:x1] = (warped * mask + roi * (1.0 - mask)).astype(np.uint8)
    return out


def audio_states(audio_path: Path, duration_step: float = 1 / FPS_MOUTH):
    with wave.open(str(audio_path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())

    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    x /= 32768.0

    duration = len(x) / sr
    count = math.ceil(duration / duration_step)

    rms = []
    for i in range(count):
        a = int(i * duration_step * sr)
        b = min(len(x), int((i + 1) * duration_step * sr))
        seg = x[a:b]
        rms.append(float(np.sqrt(np.mean(seg * seg))) if len(seg) else 0.0)

    rms = np.asarray(rms)
    if len(rms) >= 3:
        rms = np.convolve(rms, np.ones(3) / 3.0, mode="same")

    silence = max(0.010, float(np.percentile(rms, 30)) * 0.9)
    medium = max(silence * 1.7, float(np.percentile(rms, 62)))

    states = []
    previous = 2
    for value in rms:
        state = 2 if value < silence else 1 if value < medium else 0

        # Avoid unnatural direct jumps between fully open and most closed.
        if abs(state - previous) > 1:
            state = 1

        states.append(state)
        previous = state

    return states, duration, duration_step


def main():
    master = np.asarray(Image.open(MASTER).convert("RGB"))

    # 0=open, 1=medium, 2=more closed.
    amounts = [0.0, 0.45, 0.90]
    for idx, amount in enumerate(amounts):
        Image.fromarray(make_mouth_state(master, amount)).save(
            OUTDIR / f"mouth_state_{idx}.png"
        )

    states, duration, step = audio_states(AUDIO)

    chunks = []
    current = states[0]
    n = 1
    for state in states[1:]:
        if state == current:
            n += 1
        else:
            chunks.append((current, n * step))
            current = state
            n = 1
    chunks.append((current, n * step))

    excess = sum(d for _, d in chunks) - duration
    chunks[-1] = (chunks[-1][0], max(0.02, chunks[-1][1] - excess))

    concat = OUTDIR / "mouth_concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for state, seconds in chunks:
            path = (OUTDIR / f"mouth_state_{state}.png").resolve()
            f.write(f"file '{path}'\n")
            f.write(f"duration {seconds:.4f}\n")
        f.write(f"file '{(OUTDIR / f'mouth_state_{chunks[-1][0]}.png').resolve()}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat),
            "-i", str(AUDIO),
            "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            str(OUTDIR / "cat_lipsync_v4.mp4"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
