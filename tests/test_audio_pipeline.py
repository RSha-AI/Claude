import wave

import pytest

from app.pipeline.audio_pipeline import SAMPLE_RATE, split_for_conversion


def _write_silence(path, seconds):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"\x00\x00" * int(SAMPLE_RATE * seconds))
    return path


def test_no_range_uses_whole_file_without_ffmpeg(tmp_path):
    wav = _write_silence(tmp_path / "a.wav", 1.0)
    segments = split_for_conversion(wav, tmp_path, None, None)
    assert segments.before is None and segments.after is None
    assert segments.target == wav


@pytest.mark.parametrize(
    "start,end",
    [
        (0.0, 0.0),  # 길이 0 구간
        (1.5, 1.0),  # 시작 > 종료
        (5.0, None),  # 시작이 영상 길이(2초) 이후
        (-1.0, 1.0),  # 음수 시작
    ],
)
def test_invalid_range_is_rejected_with_clear_message(tmp_path, start, end):
    wav = _write_silence(tmp_path / "a.wav", 2.0)
    with pytest.raises(ValueError, match="변환 구간"):
        split_for_conversion(wav, tmp_path, start, end)
