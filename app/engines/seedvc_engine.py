"""Seed-VC 기반 제로샷 즉석 변환 엔진.

좌측에 영상/음성 파일을 업로드했을 때 사용. 레퍼런스 음성 1~30초만 있으면
별도 학습 없이 그 목소리로 변환한다. (Seed-VC는 레퍼런스 앞 25초만 사용)

Seed-VC는 third_party/seed-vc 에 클론하고 그 안의 .venv 에 의존성을 설치한
외부 저장소다(third_party/README.md 참고). CLI 인자는 app/config.py의
SEEDVC_INFER_ARGS 에서 관리한다. 첫 실행 시 모델 가중치를 Hugging Face에서
third_party/seed-vc/checkpoints/ 로 자동 다운로드한다.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.config import (
    SEEDVC_DIFFUSION_STEPS,
    SEEDVC_INFER_ARGS,
    SEEDVC_PYTHON,
    SEEDVC_REPO_DIR,
    TMP_DIR,
)
from app.engines.base import EngineError, VoiceConversionEngine, run_engine_process
from app.pipeline.audio_pipeline import extract_audio


class SeedVCEngine(VoiceConversionEngine):
    def __init__(self, reference_media: Path):
        """reference_media: 좌측에서 업로드한 목소리 레퍼런스 영상/음성 (1~30초 권장)."""
        self.reference_media = reference_media
        self._reference_wav: Path | None = None

    def is_ready(self) -> tuple[bool, str]:
        script = SEEDVC_REPO_DIR / "inference.py"
        if not script.exists():
            return False, (
                f"Seed-VC 저장소를 찾을 수 없습니다: {script}\n"
                "third_party/README.md 안내에 따라 저장소를 클론하세요."
            )
        if not SEEDVC_PYTHON.exists():
            return False, (
                f"Seed-VC 전용 가상환경이 없습니다: {SEEDVC_PYTHON}\n"
                "third_party/README.md 안내에 따라 의존성을 설치하세요."
            )
        if not self.reference_media.exists():
            return False, f"레퍼런스 파일이 없습니다: {self.reference_media}"
        return True, ""

    def _prepare_reference(self) -> Path:
        """영상/mp3 등 어떤 형식이든 Seed-VC가 읽을 수 있는 WAV로 1회 변환해 둔다."""
        if self._reference_wav is None or not self._reference_wav.exists():
            # 고정 경로를 덮어써서 임시 파일이 쌓이지 않게 한다.
            self._reference_wav = extract_audio(
                self.reference_media, TMP_DIR / "seedvc_reference.wav"
            )
        return self._reference_wav

    def convert(self, source_wav: Path, out_wav: Path) -> Path:
        ready, msg = self.is_ready()
        if not ready:
            raise EngineError(msg)

        reference_wav = self._prepare_reference()
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        # Seed-VC는 출력 파일명을 스스로 정하므로 빈 임시 폴더에 받은 뒤 옮긴다.
        run_dir = Path(tempfile.mkdtemp(prefix="seedvc_out_", dir=out_wav.parent))
        try:
            values = {
                "source_wav": str(source_wav.resolve()),
                "reference_wav": str(reference_wav.resolve()),
                "out_dir": str(run_dir.resolve()),
                "diffusion_steps": str(SEEDVC_DIFFUSION_STEPS),
            }
            args = [a.format(**values) for a in SEEDVC_INFER_ARGS]
            run_engine_process(SEEDVC_PYTHON, args, SEEDVC_REPO_DIR, "Seed-VC 변환")

            produced = sorted(run_dir.glob("*.wav"))
            if not produced:
                raise EngineError(f"Seed-VC 변환 결과 파일을 찾을 수 없습니다: {run_dir}")
            shutil.move(str(produced[0]), str(out_wav))
            return out_wav
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)
