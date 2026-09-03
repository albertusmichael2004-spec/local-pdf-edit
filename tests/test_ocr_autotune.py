import json
from pathlib import Path

import pytest

from backend.services.shared.ocr.profile import OCRProfile, load_active_profile
from training.ocr.fitness import summarize
from training.ocr.dataset import load_split
from training.ocr.gate import regression_gate
from training.ocr.metrics import error_rates, suspicious_token_ratio
from training.ocr.optimizer import EvolutionaryOptimizer
from training.ocr.policy import AdaptivePolicy


def test_profile_round_trip_and_invalid_champion_fallback(monkeypatch, tmp_path: Path):
    profile = OCRProfile(primary_psm=6, clahe_clip_limit=2.5).validate()
    assert OCRProfile.from_dict(profile.to_dict()) == profile
    invalid = tmp_path / "champion.json"
    invalid.write_text('{"primary_psm": 999}', encoding="utf-8")
    monkeypatch.setenv("OCR_PROFILE_PATH", str(invalid))
    assert load_active_profile() == OCRProfile()


def test_normalized_metrics_detect_edits_and_noise():
    cer, wer = error_rates("Halo dunia", "Halo bumi")
    assert 0 < cer < 1
    assert wer == 0.5
    assert suspicious_token_ratio("normal ###@@ token") > 0


def test_fitness_tracks_worst_page_and_categories():
    rows = [
        {"category": "photo", "cer": 0.1, "wer": 0.2, "duplicate_ratio": 0,
         "suspicious_ratio": 0, "runtime_seconds": 2},
        {"category": "scan", "cer": 0.3, "wer": 0.4, "duplicate_ratio": 0,
         "suspicious_ratio": 0, "runtime_seconds": 4},
    ]
    result = summarize(rows, 10)
    assert result["mean_cer"] == pytest.approx(0.2)
    assert result["worst_cer"] == 0.3
    assert set(result["category_cer"]) == {"photo", "scan"}


def test_optimizer_is_bounded(tmp_path: Path):
    space = {"primary_psm": {"type": "choice", "values": [3, 6]}}
    path = tmp_path / "space.json"
    path.write_text(json.dumps(space), encoding="utf-8")
    candidate = EvolutionaryOptimizer(path, 7).mutate(OCRProfile(), 1, 0.3)
    assert candidate.primary_psm == 6


def test_dataset_maps_generic_languages_to_installed_models():
    samples = load_split(Path("training/ocr"), "train", "eng+ind")
    assert next(item for item in samples if item.sample_id == "sample_001").language == "ind"
    assert next(item for item in samples if item.sample_id == "web_handwriting_001").language == "eng"


def test_policy_learns_best_profile_for_nearby_features():
    first, second = OCRProfile(primary_psm=3), OCRProfile(primary_psm=6)
    names = (
        "brightness", "contrast", "blur", "noise", "aspect_ratio", "edge_density",
        "text_density", "estimated_skew", "document_coverage", "contour_density",
        "background_uniformity",
    )
    rows = []
    for index, profile in enumerate((first, second)):
        rows.append({
            "sample_id": str(index), "sample_loss": 0.1,
            "features": {name: float(index) for name in names},
            "profile_hash": str(index), "profile": profile.to_dict(),
        })
    model = AdaptivePolicy.fit(rows, neighbors=1)
    assert model.predict_features({name: 0.05 for name in names}).primary_psm == 3


def test_regression_gate_rejects_worst_page_regression():
    incumbent = {"loss": 0.2, "mean_cer": 0.1, "mean_wer": 0.2,
                 "worst_cer": 0.2, "duplicate_ratio": 0, "category_cer": {"a": 0.1}}
    candidate = dict(incumbent, loss=0.19, worst_cer=0.4)
    passed, reasons = regression_gate(candidate, incumbent, 0.03)
    assert not passed
    assert any("worst_cer" in reason for reason in reasons)
