from pathlib import Path

import pytest
from PIL import Image

from curation.models import Candidate, ImageRef


@pytest.fixture
def candidate():
    return Candidate(id="aic-1", source="aic", title="Sky", artist="Painter", date="1900", image=ImageRef(url="https://example.com/a.jpg", thumbUrl="https://example.com/t.jpg"), sourceUrl="https://example.com/work", credit="Public Domain")


@pytest.fixture
def image_file(tmp_path: Path):
    path = tmp_path / "image.jpg"
    Image.new("RGB", (30, 30), (220, 150, 100)).save(path)
    return path

