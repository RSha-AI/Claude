"""오디오 추출/구간 분할/변환 결과 재조립 파이프라인.

처리 순서 (스펙 5.오디오 처리 파이프라인 참고):
1. 영상에서 ffmpeg로 오디오 추출
2. 구간 지정이 있으면 [시작 전] + [지정 구간] + [지정 구간 이후] 3조각으로 분할.
   구간 지정이 없으면 전체를 하나의 조각으로 취급.
3. (호출자 책임) 지정 구간만 변환 엔진에 통과시켜 목소리 교체
4. 분할했던 조각을 원래 순서로 재결합
"""

from __future__ import annotations

import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from app.config import FFMPEG_BIN

SAMPLE_RATE = 44100


class FfmpegError(RuntimeError):
    pass


def run_ffmpeg(args: list[str]) -> None:
    cmd = [FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"ffmpeg 실패 (exit={result.returncode}): {result.stderr.strip()}")


def extract_audio(video_path: Path, out_wav_path: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    """영상에서 오디오 트랙을 PCM WAV로 추출한다."""
    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", "1",
            str(out_wav_path),
        ]
    )
    return out_wav_path


def get_wav_duration_seconds(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def _slice_wav(src: Path, dst: Path, start: float | None, end: float | None) -> Path:
    """src WAV에서 [start, end) 초 구간만 잘라 dst에 저장한다.

    start=None -> 0초부터, end=None -> 끝까지.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(src)]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    if end is not None:
        duration = end - (start or 0.0)
        args += ["-t", f"{max(duration, 0.0):.3f}"]
    args += ["-acodec", "pcm_s16le", str(dst)]
    run_ffmpeg(args)
    return dst


@dataclass
class AudioSegments:
    """구간 지정 변환을 위한 3조각. before/after는 구간 지정이 없거나
    시작이 0초 / 끝이 영상 끝이면 None이 된다."""

    before: Path | None
    target: Path
    after: Path | None


def split_for_conversion(
    wav_path: Path,
    tmp_dir: Path,
    start: float | None,
    end: float | None,
) -> AudioSegments:
    """전체 오디오를 [시작 전] / [지정 구간] / [지정 구간 이후]로 분할한다.

    start, end가 모두 None이면 전체를 target으로 사용(before/after 없음).
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)

    if start is None and end is None:
        return AudioSegments(before=None, target=wav_path, after=None)

    duration = get_wav_duration_seconds(wav_path)
    start = start or 0.0
    end = min(end, duration) if end is not None else duration
    if start < 0 or start >= end:
        raise ValueError(
            f"변환 구간이 올바르지 않습니다: 시작 {start:.2f}초 / 종료 {end:.2f}초 "
            f"(영상 길이 {duration:.2f}초)"
        )

    before = None
    if start > 0.0:
        before = _slice_wav(wav_path, tmp_dir / "part_before.wav", None, start)

    target = _slice_wav(wav_path, tmp_dir / "part_target.wav", start, end)

    after = None
    if end < duration:
        after = _slice_wav(wav_path, tmp_dir / "part_after.wav", end, None)

    return AudioSegments(before=before, target=target, after=after)


def concat_wavs(parts: list[Path], out_path: Path) -> Path:
    """여러 WAV 조각을 순서대로 이어붙인다 (ffmpeg concat demuxer 사용)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        run_ffmpeg(["-i", str(parts[0]), "-acodec", "pcm_s16le", str(out_path)])
        return out_path

    list_file = out_path.parent / f"{out_path.stem}_concat_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts), encoding="utf-8"
    )
    run_ffmpeg(
        [
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-acodec", "pcm_s16le",
            str(out_path),
        ]
    )
    list_file.unlink(missing_ok=True)
    return out_path


def conform_to(src: Path, reference: Path, dst: Path) -> Path:
    """src를 reference와 같은 포맷(SAMPLE_RATE, mono, s16)과 정확히 같은 길이로 맞춘다.

    변환 엔진 출력은 샘플레이트가 제각각(Seed-VC 22.05k, RVC 40k)이고 길이도 수 ms씩
    달라질 수 있다. 그대로 이어붙이면 concat이 깨지거나 영상과 싱크가 밀리므로,
    리샘플 후 부족하면 무음으로 채우고 넘치면 자른다.
    """
    duration = get_wav_duration_seconds(reference)
    run_ffmpeg(
        [
            "-i", str(src),
            "-af", "apad",
            "-t", f"{duration:.6f}",
            "-ar", str(SAMPLE_RATE),
            "-ac", "1",
            "-acodec", "pcm_s16le",
            str(dst),
        ]
    )
    return dst


def reassemble(segments: AudioSegments, converted_target: Path, out_path: Path) -> Path:
    """변환된 target 조각을 before/after 원본과 원래 순서로 재결합한다."""
    conformed = conform_to(
        converted_target, segments.target, out_path.parent / "converted_conformed.wav"
    )
    parts = [p for p in (segments.before, conformed, segments.after) if p is not None]
    return concat_wavs(parts, out_path)
