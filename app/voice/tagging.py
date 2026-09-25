"""보이스 라이브러리에 저장할 음성의 자동 태깅.

1차 분류: F0(기본 주파수) 분석으로 남/여 분류 -> 신뢰도 높음.
2차 추천: jitter/shimmer 등 음향 지표로 허스키함/중저음 등 톤을 추정 -> 참고용,
          정확도는 완벽하지 않으므로 UI에서 사용자가 직접 수정 가능해야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.config import GENDER_F0_THRESHOLD_HZ

try:
    import librosa
except ImportError:  # pragma: no cover - librosa is a runtime dependency
    librosa = None


@dataclass
class VoiceTags:
    gender: str  # "male" | "female"
    mean_f0_hz: float
    tone_hints: list[str] = field(default_factory=list)
    confidence: str = "auto"  # "auto" | "user_edited"


def _require_librosa() -> None:
    if librosa is None:
        raise RuntimeError(
            "librosa가 설치되어 있지 않습니다. requirements.txt를 통해 설치하세요."
        )


def estimate_f0(y: np.ndarray, sr: int) -> float:
    """유성음 구간의 평균 F0(Hz)를 추정한다. 무음/무성음만 있으면 0.0을 반환."""
    _require_librosa()
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    voiced_f0 = f0[voiced_flag] if voiced_flag is not None else np.array([])
    voiced_f0 = voiced_f0[~np.isnan(voiced_f0)]
    if voiced_f0.size == 0:
        return 0.0
    return float(np.median(voiced_f0))


def classify_gender(mean_f0_hz: float) -> str:
    """F0 임계값 기준 1차 성별 분류. 신뢰도가 높은 편이지만 100%는 아니다."""
    if mean_f0_hz <= 0:
        return "unknown"
    return "male" if mean_f0_hz < GENDER_F0_THRESHOLD_HZ else "female"


def estimate_jitter_shimmer(y: np.ndarray, sr: int) -> tuple[float, float]:
    """간이 jitter(주기 변동률)/shimmer(진폭 변동률) 추정.

    정밀한 임상용 지표가 아니라, 톤 추천을 위한 참고 수치임에 유의.
    """
    _require_librosa()
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    voiced_f0 = f0[voiced_flag] if voiced_flag is not None else np.array([])
    voiced_f0 = voiced_f0[~np.isnan(voiced_f0)]
    if voiced_f0.size < 2:
        jitter = 0.0
    else:
        periods = 1.0 / voiced_f0
        jitter = float(np.mean(np.abs(np.diff(periods))) / np.mean(periods))

    frame_len = int(sr * 0.02) or 1
    n_frames = max(len(y) // frame_len, 1)
    amps = np.array(
        [
            np.sqrt(np.mean(np.square(y[i * frame_len : (i + 1) * frame_len])) + 1e-12)
            for i in range(n_frames)
        ]
    )
    if amps.size < 2 or np.mean(amps) == 0:
        shimmer = 0.0
    else:
        shimmer = float(np.mean(np.abs(np.diff(amps))) / np.mean(amps))

    return jitter, shimmer


def suggest_tone_hints(mean_f0_hz: float, jitter: float, shimmer: float) -> list[str]:
    """jitter/shimmer/F0로부터 참고용 톤 태그를 추천한다 (허스키함, 중저음 등)."""
    hints: list[str] = []
    if mean_f0_hz > 0 and mean_f0_hz < 120:
        hints.append("중저음")
    if jitter > 0.02 or shimmer > 0.12:
        hints.append("허스키함")
    if not hints:
        hints.append("표준톤")
    return hints


def auto_tag(y: np.ndarray, sr: int) -> VoiceTags:
    """음성 샘플(y, sr)로부터 자동 태그 전체를 생성한다."""
    mean_f0 = estimate_f0(y, sr)
    gender = classify_gender(mean_f0)
    jitter, shimmer = estimate_jitter_shimmer(y, sr)
    hints = suggest_tone_hints(mean_f0, jitter, shimmer)
    return VoiceTags(gender=gender, mean_f0_hz=mean_f0, tone_hints=hints)
