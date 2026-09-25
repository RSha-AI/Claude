"""음성 변환 엔진 공통 인터페이스.

두 엔진(Seed-VC 제로샷 / RVC 사전 학습)을 이 인터페이스로 통일해서
파이프라인/GUI 쪽 코드가 어떤 엔진이든 동일하게 호출할 수 있게 한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class VoiceConversionEngine(ABC):
    """target_wav 구간(source_wav)의 목소리를 원하는 목소리로 바꾼다."""

    @abstractmethod
    def convert(self, source_wav: Path, out_wav: Path) -> Path:
        """source_wav를 변환해 out_wav로 저장하고 out_wav를 반환한다."""
        raise NotImplementedError

    def is_ready(self) -> tuple[bool, str]:
        """엔진 실행에 필요한 의존성(외부 저장소, 모델 파일 등)이 준비됐는지 확인한다.

        Returns: (준비 여부, 준비 안 됐을 때 사용자에게 보여줄 안내 메시지)
        """
        return True, ""
