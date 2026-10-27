from pathlib import Path

import numpy as np
import yaml
from PIL import Image


def load_prompts(path: Path | None = None) -> dict:
    path = path or Path(__file__).with_name("prompts.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class OpenClipClassifier:
    """Lazy optional CLIP backend; importing curation never imports torch."""

    def __init__(self, model_name="ViT-B-32", pretrained="laion2b_s34b_b79k", device=None):
        try:
            import open_clip
            import torch
        except ImportError as exc:
            raise RuntimeError("Install the CLIP extra: uv sync --extra clip") from exc
        self.torch, self.open_clip = torch, open_clip
        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained, device=device)
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.eval()

    def predict(self, image_path: Path, prompts: dict | None = None) -> dict[str, dict[str, float]]:
        prompts = prompts or load_prompts()
        result = {}
        torch = self.torch
        image = self.preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            image_features = self.model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            for axis, categories in prompts.items():
                category_scores = []
                for texts in categories.values():
                    tokens = self.tokenizer(texts).to(self.device)
                    features = self.model.encode_text(tokens)
                    features /= features.norm(dim=-1, keepdim=True)
                    category_scores.append((image_features @ features.T).mean().item())
                probs = np.exp(category_scores - np.max(category_scores))
                probs /= probs.sum()
                result[axis] = dict(zip(categories, map(float, probs), strict=True))
        return result

