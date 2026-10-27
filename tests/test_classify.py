import warnings

from PIL import Image

from curation.classify.color import analyze_color
from curation.classify.service import classify_one


class FakeClassifier:
    def predict(self, path):
        return {"sky": {"visible": .9, "hidden": .1}, "weather": {"clear": .8, "cloudy": .2}, "time": {"day": .7, "twilight": .3}, "season": {"summer": .8, "winter": .2}}


def test_color_and_classify(candidate, image_file):
    features = analyze_color(image_file)
    assert features["brightness"] > 0.5
    result = classify_one(candidate, image_file, FakeClassifier(), .4)
    assert result.sky_visible
    assert result.tags.weather == ["clear"]
    assert "summer" in result.tags.season


def test_black_image_color_analysis_has_no_runtime_warning(tmp_path):
    path = tmp_path / "black.png"
    Image.new("RGB", (20, 20), (0, 0, 0)).save(path)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        features = analyze_color(path)
    assert features["brightness"] == 0
    assert features["saturation"] == 0
