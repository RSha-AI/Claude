"""새 목소리를 RVC로 학습해서 보이스 라이브러리에 등록하는 CLI.

사용 예:
    python scripts/train_voice.py \
        --name "그록-남성1" --gender male --dataset "D:/tts_samples/grok_male1" \
        --memo "그록 기본 음성"

dataset 폴더에는 그록/일레븐랩스/타입캐스트 등에서 뽑은 깨끗한 TTS wav 파일들을
넣어둔다. 학습은 1회성 작업이며(RTX 2070 기준 수십 분 소요 추정), 완료 후
결과 .pth/.index 를 app.config.MODELS_DIR 로 옮기고 라이브러리에 자동 등록한다.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import MODELS_DIR, RVC_REPO_DIR, ensure_data_dirs  # noqa: E402
from app.engines.rvc_engine import train_rvc_voice  # noqa: E402
from app.voice.library import VoiceLibrary  # noqa: E402


def find_trained_artifacts(exp_name: str) -> tuple[Path | None, Path | None]:
    """RVC 학습 결과 폴더에서 .pth/.index 파일을 찾는다.

    RVC 저장소 버전마다 출력 위치가 다를 수 있으므로, 못 찾으면 None을 반환하고
    사용자가 --pth/--index 옵션으로 직접 경로를 지정하게 한다.
    """
    exp_dir = RVC_REPO_DIR / "logs" / exp_name
    if not exp_dir.exists():
        return None, None
    pth = next(exp_dir.glob("*.pth"), None)
    index = next(exp_dir.glob("*.index"), None)
    return pth, index


def main() -> int:
    parser = argparse.ArgumentParser(description="RVC 목소리 학습 + 라이브러리 등록")
    parser.add_argument("--name", required=True, help="라이브러리에 표시할 이름")
    parser.add_argument("--gender", required=True, choices=["male", "female"])
    parser.add_argument("--dataset", required=True, help="깨끗한 TTS wav 샘플 폴더")
    parser.add_argument("--memo", default="")
    parser.add_argument("--pth", help="학습 후 자동 탐색 실패 시 직접 지정할 .pth 경로")
    parser.add_argument("--index", help="학습 후 자동 탐색 실패 시 직접 지정할 .index 경로")
    args = parser.parse_args()

    ensure_data_dirs()
    exp_name = args.name.replace(" ", "_")
    dataset_dir = Path(args.dataset)

    print(f"[1/3] '{args.name}' 학습 시작 (exp={exp_name})...")
    train_rvc_voice(exp_name, dataset_dir)

    print("[2/3] 학습 결과 탐색 중...")
    pth, index = find_trained_artifacts(exp_name)
    if args.pth:
        pth = Path(args.pth)
    if args.index:
        index = Path(args.index)
    if pth is None or not pth.exists():
        print("모델 파일(.pth)을 자동으로 찾지 못했습니다. --pth 옵션으로 경로를 지정하세요.")
        return 1

    dest_pth = MODELS_DIR / f"{exp_name}.pth"
    shutil.copy2(pth, dest_pth)
    dest_index = ""
    if index and index.exists():
        dest_index_path = MODELS_DIR / f"{exp_name}.index"
        shutil.copy2(index, dest_index_path)
        dest_index = str(dest_index_path)

    print("[3/3] 보이스 라이브러리에 등록 중...")
    library = VoiceLibrary()
    library.add(
        name=args.name,
        gender=args.gender,
        model_path=str(dest_pth),
        index_path=dest_index,
        memo=args.memo,
    )
    print(f"완료: {args.name} -> {dest_pth}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
