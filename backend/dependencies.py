"""Cached model dependency used by recommendation routes."""

import os
from functools import lru_cache
from pathlib import Path
from fastapi import HTTPException
from recommendations.artifacts import load_artifact
from recommendations.inference import ServingModel

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "als-model.npz"


@lru_cache(maxsize=1)
def load_model(path: str) -> ServingModel:
    return load_artifact(Path(path))


def get_serving_model() -> ServingModel:
    path = Path(os.environ.get("MUSIC_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
    try:
        return load_model(str(path.resolve()))
    except (OSError, ValueError, KeyError) as error:
        raise HTTPException(503, detail="Recommendation model is unavailable.") from error
