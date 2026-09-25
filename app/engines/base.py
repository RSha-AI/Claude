"""음성 변환 엔진 공통 인터페이스.

두 엔진(Seed-VC 제로샷 / RVC 사전 학습)을 이 인터페이스로 통일해서
파이프라인/GUI 쪽 코드가 어떤 엔진이든 동일하게 호출할 수 있게 한다.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from app.config import engine_env

LogCallback = Callable[[str], None]


class EngineError(RuntimeError):
    pass


def run_engine_process(
    python: Path,
    args: list[str],
    cwd: Path,
    what: str,
    on_log: LogCallback | None = None,
) -> str:
    """외부 엔진 스크립트를 해당 엔진 전용 python으로 실행하고 전체 출력을 반환한다.

    on_log가 주어지면 출력을 줄 단위로 실시간 전달한다(학습처럼 오래 걸리는 작업용).
    실패 시 출력 마지막 부분을 담아 EngineError를 던진다.
    """
    env = engine_env()
    # 엔진 스크립트들은 저장소 루트 기준 import(`from infer.audio import ...`)를 쓴다.
    # 또 RVC의 train/preprocess.py 등은 스크립트 폴더(train/)가 sys.path에 들어가면
    # `train` 패키지 대신 train/train.py가 import되어 깨진다. RVC 공식 포터블 런타임과
    # 같은 조건을 만들기 위해 -P(스크립트 폴더 prepend 금지) + PYTHONPATH=저장소 루트.
    env["PYTHONPATH"] = str(cwd)
    proc = subprocess.Popen(
        [str(python), "-P", *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        lines.append(line)
        if on_log:
            on_log(line)
    proc.wait()
    output = "\n".join(lines)
    if proc.returncode != 0:
        tail = "\n".join(lines[-30:])
        raise EngineError(f"{what} 실패 (exit={proc.returncode}):\n{tail}")
    return output


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
