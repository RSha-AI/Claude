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

# --- 외부 엔진 실행 커맨드 템플릿 -------------------------------------------------
# Seed-VC / RVC는 둘 다 활발히 개발 중인 외부 프로젝트라 스크립트 경로나 인자 이름이
# 버전에 따라 달라질 수 있다. 하드코딩 대신 템플릿으로 분리해두었으니, third_party/에
# 클론한 저장소의 실제 CLI에 맞게 이 값들만 수정하면 된다. (app/engines/*.py는 이
# 템플릿을 그대로 사용하므로 코드를 고칠 필요가 없다.)
PYTHON_BIN = sys.executable

SEEDVC_INFER_CMD_TEMPLATE = (
    '"{python}" "{seedvc_dir}/inference.py" '
    '--source "{source_wav}" --target "{reference_wav}" --output "{out_dir}"'
)

RVC_INFER_CMD_TEMPLATE = (
    '"{python}" "{rvc_dir}/tools/infer_cli.py" '
    '--input_path "{source_wav}" --model_path "{model_path}" '
    '--index_path "{index_path}" --opt_path "{out_wav}"'
)

RVC_TRAIN_CMD_TEMPLATE = (
    '"{python}" "{rvc_dir}/train_cli.py" '
    '--exp_name "{exp_name}" --dataset_dir "{dataset_dir}" --sample_rate 40000'
)
