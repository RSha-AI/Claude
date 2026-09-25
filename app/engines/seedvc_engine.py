"""Seed-VC 기반 제로샷 즉석 변환 엔진.

좌측에 영상/음성 파일을 업로드했을 때 사용. 레퍼런스 음성 1~30초만 있으면
별도 학습 없이 그 목소리로 변환한다.

주의: Seed-VC는 third_party/seed-vc 에 사용자가 직접 클론해야 하는 외부 저장소다
(third_party/README.md 참고). 정확한 CLI 인자는 클론한 버전에 따라 달라질 수 있으므로
app/config.py의 SEEDVC_INFER_CMD_TEMPLATE 을 실제 설치된 버전에 맞게 조정한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import PYTHON_BIN, SEEDVC_INFER_CMD_TEMPLATE, SEEDVC_REPO_DIR
from app.engines.base import VoiceConversionEngine


class SeedVCEngine(VoiceConversionEngine):
    def __init__(self, reference_wav: Path):
        """reference_wav: 좌측에서 업로드한 목소리 레퍼런스 (1~30초 권장)."""
        self.reference_wav = reference_wav

    def is_ready(self) -> tuple[bool, str]:
        script = SEEDVC_REPO_DIR / "inference.py"
        if not script.exists():
            return False, (
                f"Seed-VC 저장소를 찾을 수 없습니다: {script}\n"
                "third_party/README.md 안내에 따라 저장소를 클론하세요."
            )
        if not self.reference_wav.exists():
            return False, f"레퍼런스 음성 파일이 없습니다: {self.reference_wav}"
        return True, ""

    def convert(self, source_wav: Path, out_wav: Path) -> Path:
        ready, msg = self.is_ready()
        if not ready:
            raise RuntimeError(msg)

        out_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = SEEDVC_INFER_CMD_TEMPLATE.format(
            python=PYTHON_BIN,
            seedvc_dir=str(SEEDVC_REPO_DIR),
            source_wav=str(source_wav),
            reference_wav=str(self.reference_wav),
            out_dir=str(out_wav.parent),
        )
        # shell=True 사용: 템플릿에 이미 각 경로가 따옴표로 감싸져 있어
        # Windows/POSIX 양쪽 경로(백슬래시 포함)를 shlex 없이 안전하게 처리한다.
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Seed-VC 변환 실패: {result.stderr.strip()}")
        return out_wav
