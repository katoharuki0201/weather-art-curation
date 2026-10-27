from ..categories import TIMES, WEATHER
from ..models import AxisScores, Tags


def _normalized(values: dict[str, float]) -> dict[str, float]:
    total = sum(max(0, value) for value in values.values()) or 1
    return {key: max(0, value) / total for key, value in values.items()}


def combine(scores: dict[str, dict[str, float]], color: dict[str, float], threshold: float = 0.25):
    adjusted = {axis: dict(values) for axis, values in scores.items()}
    weather = adjusted.setdefault("weather", {})
    times = adjusted.setdefault("time", {})
    brightness, warmth, gray = color.get("brightness", 0.5), color.get("warmth", 0), color.get("gray_fraction", 0)
    times["night"] = times.get("night", 0) + max(0, 0.35 - brightness) * 0.8
    times["twilight"] = times.get("twilight", 0) + max(0, warmth) * 0.45
    weather["cloudy"] = weather.get("cloudy", 0) + gray * 0.2
    for axis in adjusted:
        adjusted[axis] = _normalized(adjusted[axis])

    def select(axis, allowed, required=True):
        values = adjusted.get(axis, {})
        chosen = [key for key in allowed if values.get(key, 0) >= threshold]
        if required and not chosen and values:
            chosen = [max(values, key=values.get)]
        return chosen

    tags = Tags(weather=select("weather", WEATHER), time=select("time", TIMES))
    margins = []
    for axis in ("weather", "time"):
        ranked = sorted(adjusted.get(axis, {}).values(), reverse=True)
        if ranked:
            margins.append(ranked[0] - (ranked[1] if len(ranked) > 1 else 0))
    confidence = min(1.0, max(0.0, sum(margins) / len(margins) if margins else 0))
    return tags, AxisScores(**adjusted), confidence
