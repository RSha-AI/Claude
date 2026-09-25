"""RVC(사전 학습) 기반 음성 변환 엔진.

좌측 드롭다운에서 학습된 보이스 라이브러리를 선택했을 때 사용. 그록/일레븐랩스/
타입캐스트 등에서 뽑은 깨끗한 TTS 음성으로 목소리별 모델을 미리 학습해두고,
.pth(+index) 체크포인트로 영구 저장한다.

주의: RVC는 third_party/rvc 에 사용자가 직접 클론해야 하는 외부 저장소다
(third_party/README.md 참고). 정확한 학습/추론 CLI는 클론한 버전에 따라 달라질 수
있으므로 app/config.py의 RVC_INFER_CMD_TEMPLATE / RVC_TRAIN_CMD_TEMPLATE 을 실제
설치된 버전에 맞게 조정한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import (
    PYTHON_BIN,
    RVC_INFER_CMD_TEMPLATE,
    RVC_REPO_DIR,
    RVC_TRAIN_CMD_TEMPLATE,
)
from app.engines.base import VoiceConversionEngine


class RVCEngine(VoiceConversionEngine):
    def __init__(self, model_path: Path, index_path: Path | None = None):
        """model_path: 보이스 라이브러리에 저장된 .pth 체크포인트.
        index_path: 함께 저장된 .index 파일 (있으면 검색 품질 향상)."""
        self.model_path = model_path
        self.index_path = index_path

    def is_ready(self) -> tuple[bool, str]:
        script = RVC_REPO_DIR / "tools" / "infer_cli.py"
        if not script.exists():
            return False, (
                f"RVC 저장소를 찾을 수 없습니다: {script}\n"
                "third_party/README.md 안내에 따라 저장소를 클론하세요."
            )
        if not self.model_path.exists():
            return False, f"모델 파일이 없습니다: {self.model_path}"
        return True, ""

    def convert(self, source_wav: Path, out_wav: Path) -> Path:
        ready, msg = self.is_ready()
        if not ready:
            raise RuntimeError(msg)

        out_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = RVC_INFER_CMD_TEMPLATE.format(
            python=PYTHON_BIN,
            rvc_dir=str(RVC_REPO_DIR),
            source_wav=str(source_wav),
            model_path=str(self.model_path),
            index_path=str(self.index_path or ""),
            out_wav=str(out_wav),
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"RVC 변환 실패: {result.stderr.strip()}")
        return out_wav


def train_rvc_voice(exp_name: str, dataset_dir: Path) -> None:
    """깨끗한 TTS 음성 샘플 폴더(dataset_dir)로부터 새 목소리를 1회 학습한다.

    RTX 2070(VRAM 8GB) 기준 목소리당 수십 분 소요 예상. 학습 결과(.pth/.index)는
    RVC 저장소의 출력 규칙에 따라 생성되며, 학습 완료 후 app.voice.library.VoiceLibrary
    에 등록해서 재사용한다.
    """
    script = RVC_REPO_DIR / "train_cli.py"
    if not script.exists():
        raise RuntimeError(
            f"RVC 학습 스크립트를 찾을 수 없습니다: {script}\n"
            "third_party/README.md 안내에 따라 저장소를 클론하세요."
        )
    if not dataset_dir.exists() or not any(dataset_dir.iterdir()):
        raise RuntimeError(f"학습용 음성 데이터가 비어 있습니다: {dataset_dir}")

    cmd = RVC_TRAIN_CMD_TEMPLATE.format(
        python=PYTHON_BIN,
        rvc_dir=str(RVC_REPO_DIR),
        exp_name=exp_name,
        dataset_dir=str(dataset_dir),
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"RVC 학습 실패: {result.stderr.strip()}")
