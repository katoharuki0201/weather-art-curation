from collections import defaultdict

from .models import Classified, Tags


def evaluate(predictions: list[Classified], labels: dict[str, Tags]) -> dict:
    by_id = {item.id: item for item in predictions}
    report = {}
    for axis in ("weather", "time", "season"):
        correct = total = 0
        matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for item_id, truth in labels.items():
            if item_id not in by_id:
                continue
            expected = getattr(truth, axis)
            if not expected and axis == "season":
                continue
            actual = getattr(by_id[item_id].tags, axis)
            total += 1
            correct += bool(set(expected) & set(actual))
            matrix[expected[0] if expected else "none"][actual[0] if actual else "none"] += 1
        report[axis] = {"accuracy": correct / total if total else None, "correct": correct, "total": total, "confusion_matrix": {k: dict(v) for k, v in matrix.items()}}
    return report

