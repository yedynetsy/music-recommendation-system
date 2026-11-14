"""Save and load portable ALS artifacts without historical user identities."""

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import numpy as np

from .als import ALSConfig, ALSRecommender
from .evaluation import EvaluationData
from .inference import ServingModel

ARTIFACT_VERSION = 1


def save_artifact(path: Path, model: ALSRecommender, data: EvaluationData,
                  cutoff: datetime, config: ALSConfig, source_sha256: str) -> str:
    """Atomically save only item factors and metadata; no listener identities."""
    if cutoff.tzinfo is None:
        raise ValueError("cutoff must include a timezone")
    if not path.parent.is_dir():
        raise ValueError("artifact parent directory does not exist")
    identity = json.dumps({"cutoff": cutoff.isoformat(), "config": asdict(config),
                           "source_sha256": source_sha256}, sort_keys=True)
    factors = model.model.item_factors.astype(np.float32, copy=False)
    digest = hashlib.sha256(identity.encode())
    digest.update(factors.tobytes())
    model_version = digest.hexdigest()[:16]
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as target:
            np.savez_compressed(
                target, format_version=np.array(ARTIFACT_VERSION),
                model_version=np.array(model_version), cutoff=np.array(cutoff.isoformat()),
                source_sha256=np.array(source_sha256),
                track_ids=np.asarray(model.track_ids),
                item_factors=factors,
                popularity=np.asarray([data.popularity[track_id]
                                       for track_id in model.track_ids], dtype=np.int64),
                alpha=np.array(config.alpha), regularization=np.array(config.regularization),
            )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return model_version


def load_artifact(path: Path) -> ServingModel:
    with np.load(path, allow_pickle=False) as artifact:
        if int(artifact["format_version"]) != ARTIFACT_VERSION:
            raise ValueError("unsupported model artifact version")
        return ServingModel(
            track_ids=artifact["track_ids"].tolist(),
            item_factors=artifact["item_factors"],
            popularity=artifact["popularity"],
            alpha=float(artifact["alpha"]),
            regularization=float(artifact["regularization"]),
            model_version=str(artifact["model_version"]),
            cutoff=str(artifact["cutoff"]),
        )
