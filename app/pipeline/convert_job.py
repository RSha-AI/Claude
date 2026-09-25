"""영상 1개에 대한 전체 변환 작업 오케스트레이션.

extract -> (구간 분할) -> 엔진 변환 -> 재조립 -> mux 까지 한 번에 처리한다.
GUI에서는 이 함수를 영상별로 백그라운드 스레드에서 순차 호출하고 진행률을 표시한다.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.config import TMP_DIR
from app.engines.base import VoiceConversionEngine
from app.pipeline.audio_pipeline import (
    extract_audio,
    reassemble,
    split_for_conversion,
)
from app.pipeline.video_pipeline import mux_video_with_audio

ProgressCallback = Callable[[str], None]


@dataclass
class ConvertRequest:
    video_path: Path
    out_video_path: Path
    start_sec: float | None = None  # 미입력 시 전체 구간 변환
    end_sec: float | None = None


def _noop(_: str) -> None:
    return None


def convert_one_video(
    request: ConvertRequest,
    engine: VoiceConversionEngine,
    on_progress: ProgressCallback = _noop,
) -> Path:
    ready, msg = engine.is_ready()
    if not ready:
        raise RuntimeError(msg)

    job_dir = TMP_DIR / f"job_{uuid.uuid4().hex[:8]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        on_progress("오디오 추출 중...")
        extracted_wav = extract_audio(request.video_path, job_dir / "extracted.wav")

        on_progress("구간 분할 중...")
        segments = split_for_conversion(
            extracted_wav, job_dir, request.start_sec, request.end_sec
        )

        on_progress("음성 변환 중...")
        converted_target = engine.convert(segments.target, job_dir / "converted_target.wav")

        on_progress("오디오 재조립 중...")
        final_audio = reassemble(segments, converted_target, job_dir / "final_audio.wav")

        on_progress("영상에 오디오 합성 중...")
        request.out_video_path.parent.mkdir(parents=True, exist_ok=True)
        mux_video_with_audio(request.video_path, final_audio, request.out_video_path)

        on_progress("완료")
        return request.out_video_path
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
