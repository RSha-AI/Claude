"""최종 영상 출력: 원본 영상의 비디오 트랙은 그대로 복사(-c:v copy)하고
오디오 트랙만 변환된 오디오로 교체한다."""

from __future__ import annotations

from pathlib import Path

from app.pipeline.audio_pipeline import run_ffmpeg


def mux_video_with_audio(original_video: Path, new_audio_wav: Path, out_video: Path) -> Path:
    out_video.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i", str(original_video),
            "-i", str(new_audio_wav),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(out_video),
        ]
    )
    return out_video
