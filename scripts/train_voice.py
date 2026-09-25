"""새 목소리를 RVC로 학습해서 보이스 라이브러리에 등록하는 CLI.

사용 예:
    python scripts/train_voice.py \
        --name "그록-남성1" --gender male --dataset "D:/tts_samples/grok_male1" \
        --memo "그록 기본 음성"

dataset 폴더에는 그록/일레븐랩스/타입캐스트 등에서 뽑은 깨끗한 TTS wav 파일들을
넣어둔다(총 10분 이상 권장). 학습은 1회성 작업이며(RTX 2070 기준 수십 분 소요 추정),
완료 후 결과 .pth/.index 를 app.config.MODELS_DIR 로 복사하고 라이브러리에 자동 등록한다.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import MODELS_DIR, RVC_TRAIN_BATCH_SIZE, RVC_TRAIN_EPOCHS, ensure_data_dirs  # noqa: E402
from app.engines.rvc_engine import train_rvc_voice  # noqa: E402
from app.voice.library import VoiceLibrary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="RVC 목소리 학습 + 라이브러리 등록")
    parser.add_argument("--name", required=True, help="라이브러리에 표시할 이름 (한글 가능)")
    parser.add_argument("--gender", required=True, choices=["male", "female"])
    parser.add_argument("--dataset", required=True, help="깨끗한 TTS wav 샘플 폴더")
    parser.add_argument("--memo", default="")
    parser.add_argument("--epochs", type=int, default=RVC_TRAIN_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=RVC_TRAIN_BATCH_SIZE)
    args = parser.parse_args()

    ensure_data_dirs()
    # 표시 이름은 한글이어도 되지만, RVC 내부 파일명은 ASCII만 안전하므로 별도 ID를 쓴다.
    exp_name = f"voice_{uuid.uuid4().hex[:8]}"
    dataset_dir = Path(args.dataset)

    print(f"[1/2] '{args.name}' 학습 시작 (exp={exp_name}, epochs={args.epochs})...", flush=True)
    result = train_rvc_voice(
        exp_name,
        dataset_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        on_log=lambda line: print(line, flush=True),
    )

    dest_pth = MODELS_DIR / f"{exp_name}.pth"
    shutil.copy2(result.model_path, dest_pth)
    dest_index = ""
    if result.index_path:
        dest_index_path = MODELS_DIR / f"{exp_name}.index"
        shutil.copy2(result.index_path, dest_index_path)
        dest_index = str(dest_index_path)

    print("[2/2] 보이스 라이브러리에 등록 중...", flush=True)
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
