from pathlib import Path

import numpy as np
from PIL import Image


def analyze_color(path: Path) -> dict[str, float]:
    image = Image.open(path).convert("RGB")
    pixels = np.asarray(image, dtype=np.float32)[: max(1, image.height // 3)] / 255.0
    maximum = pixels.max(axis=2)
    minimum = pixels.min(axis=2)
    saturation = np.where(maximum > 0, (maximum - minimum) / maximum, 0)
    luminance = pixels @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    warmth = pixels[..., 0] - pixels[..., 2]
    gray = (saturation < 0.2) & (luminance < 0.75)
    return {"brightness": float(luminance.mean()), "saturation": float(saturation.mean()), "warmth": float(warmth.mean()), "gray_fraction": float(gray.mean())}

