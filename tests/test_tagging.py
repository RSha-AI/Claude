import numpy as np
import pytest

pytest.importorskip("librosa")

from app.voice.tagging import auto_tag, classify_gender  # noqa: E402


def _sine_wave(freq_hz: float, sr: int = 22050, seconds: float = 1.0) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return 0.5 * np.sin(2 * np.pi * freq_hz * t)


def test_classify_gender_thresholds():
    assert classify_gender(100.0) == "male"
    assert classify_gender(200.0) == "female"
    assert classify_gender(0.0) == "unknown"


def test_auto_tag_low_pitch_sine_classified_male():
    sr = 22050
    y = _sine_wave(110.0, sr=sr).astype(np.float32)  # ~A2, 남성 음역대
    tags = auto_tag(y, sr)
    assert tags.gender == "male"
    assert tags.mean_f0_hz > 0
