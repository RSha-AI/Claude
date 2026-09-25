"""경로/설정 관리.

핵심 요구사항: 이 프로그램이 실행되는 PC는 재부팅 시 C드라이브가 초기화된다.
따라서 실행 파일(exe) 위치 및 사용자 데이터(보이스 라이브러리, 메타데이터, 임시 파일)는
절대로 AppData 등 C드라이브 기본 경로에 쓰지 않고, exe가 위치한 폴더를 기준으로
저장한다. 개발 중(스크립트로 실행할 때)에는 프로젝트 루트를 기준으로 삼는다.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def get_base_dir() -> Path:
    """실행 기준 폴더를 반환한다.

    - PyInstaller로 패키징된 exe로 실행 중이면: exe가 위치한 폴더.
    - 개발 중 python으로 직접 실행하면: 이 파일 기준 프로젝트 루트.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()

# 모든 사용자 데이터는 exe(또는 프로젝트 루트) 옆 data/ 폴더에 저장한다.
DATA_DIR = BASE_DIR / "data"
VOICE_LIBRARY_DIR = DATA_DIR / "voice_library"
VOICE_LIBRARY_DB = VOICE_LIBRARY_DIR / "library.json"
MODELS_DIR = DATA_DIR / "models"
TMP_DIR = DATA_DIR / "tmp"
OUTPUT_DIR = DATA_DIR / "output"

# 외부 엔진 저장소 경로 (third_party/README.md 참고)
SEEDVC_REPO_DIR = BASE_DIR / "third_party" / "seed-vc"
RVC_REPO_DIR = BASE_DIR / "third_party" / "rvc"

# 음성 성별 1차 분류 F0 임계값(Hz). 일반적으로 남성 화자 평균 F0는 약 85~180Hz,
# 여성 화자는 약 165~255Hz. 165Hz를 경계로 1차 분류하고, UI에서 사용자가
# 자동 태그를 직접 수정할 수 있게 한다.
GENDER_F0_THRESHOLD_HZ = 165.0


def ensure_data_dirs() -> None:
    """필요한 데이터 폴더를 생성한다. 프로그램 시작 시 1회 호출."""
    for d in (DATA_DIR, VOICE_LIBRARY_DIR, MODELS_DIR, TMP_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def resolve_ffmpeg_bin() -> str:
    """ffmpeg 실행 파일 경로를 찾는다.

    exe 옆 ffmpeg/ 폴더에 동봉된 바이너리를 우선 사용하고(오프라인 배포 목적),
    없으면 시스템 PATH에서 찾는다.
    """
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    bundled = BASE_DIR / "ffmpeg" / exe_name
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ffmpeg")
    return found or "ffmpeg"


FFMPEG_BIN = resolve_ffmpeg_bin()

# --- 외부 엔진 실행 설정 ----------------------------------------------------------
# Seed-VC와 RVC는 torch/transformers/gradio 버전 요구가 서로 충돌하므로 각 저장소 안에
# 전용 가상환경(.venv)을 만들어 별도 프로세스로 실행한다. (패키징된 exe에서는
# sys.executable이 exe 자신이 되므로, 이렇게 엔진별 python을 따로 지정해야 한다.)
def _venv_python(repo_dir: Path) -> Path:
    if sys.platform == "win32":
        return repo_dir / ".venv" / "Scripts" / "python.exe"
    return repo_dir / ".venv" / "bin" / "python"


SEEDVC_PYTHON = _venv_python(SEEDVC_REPO_DIR)
RVC_PYTHON = _venv_python(RVC_REPO_DIR)

# 외부 엔진 CLI 인자 템플릿. 각 항목은 str.format()으로 치환된 뒤 리스트 그대로
# subprocess에 전달된다(셸을 거치지 않으므로 한글/공백 경로도 안전). 엔진 저장소를
# 업데이트해서 CLI가 바뀌면 이 값들만 수정하면 된다. 실행 시 cwd는 각 저장소 루트.
#
# Seed-VC (inference.py, 2026-09 기준): 출력 폴더에 vc_<source>_<target>_...wav 로
# 저장하므로 엔진 쪽에서 결과 파일을 찾아 원하는 경로로 옮긴다.
SEEDVC_INFER_ARGS = [
    "inference.py",
    "--source", "{source_wav}",
    "--target", "{reference_wav}",
    "--output", "{out_dir}",
    "--diffusion-steps", "{diffusion_steps}",
    "--fp16", "True",
]
SEEDVC_DIFFUSION_STEPS = 30  # 품질/속도 트레이드오프 (공식 권장 30~50)

# RVC (infer/cli.py, 2026-09 기준). index가 없으면 --index-rate 0 으로 실행.
RVC_INFER_ARGS = [
    "infer/cli.py",
    "--model", "{model_path}",
    "--input", "{source_wav}",
    "--output", "{out_wav}",
    "--f0-method", "rmvpe",
    "--pitch", "{pitch}",
    "--overwrite",
]

# RVC 학습 파라미터 (v2 / 40k / F0 사용). RTX 2070(8GB) 기준 기본값.
RVC_TRAIN_SAMPLE_RATE = "40k"
RVC_TRAIN_EPOCHS = 200
RVC_TRAIN_SAVE_EVERY = 50
RVC_TRAIN_BATCH_SIZE = 8


def engine_env() -> dict[str, str]:
    """외부 엔진 프로세스용 환경 변수.

    - 동봉 ffmpeg 폴더를 PATH 앞에 추가 (RVC/Seed-VC 내부 오디오 로딩용)
    - 자식 파이썬 출력 인코딩을 UTF-8로 고정 (한글 경로/로그 깨짐 방지)
    """
    import os

    env = os.environ.copy()
    ffmpeg_dir = str(Path(FFMPEG_BIN).parent) if Path(FFMPEG_BIN).is_file() else ""
    if ffmpeg_dir:
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env
