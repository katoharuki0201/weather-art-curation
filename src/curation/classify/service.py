from pathlib import Path
from typing import Protocol

from ..models import Candidate, Classified
from .color import analyze_color
from .combine import combine


class Classifier(Protocol):
    def predict(self, image_path: Path) -> dict[str, dict[str, float]]: ...


def classify_one(item: Candidate, image_path: Path, classifier: Classifier, threshold: float = 0.25) -> Classified:
    raw = classifier.predict(image_path)
    color = analyze_color(image_path)
    tags, scores, confidence = combine(raw, color, threshold)
    sky_visible = raw.get("sky", {}).get("visible", 1) >= raw.get("sky", {}).get("hidden", 0)
    return Classified(**item.model_dump(by_alias=False), tags=tags, scores=scores, confidence=confidence, sky_visible=sky_visible, color_features=color)

