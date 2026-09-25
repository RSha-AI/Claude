"""RVC(사전 학습) 기반 음성 변환 엔진.

좌측 드롭다운에서 학습된 보이스 라이브러리를 선택했을 때 사용. 그록/일레븐랩스/
타입캐스트 등에서 뽑은 깨끗한 TTS 음성으로 목소리별 모델을 미리 학습해두고,
.pth(+index) 체크포인트로 영구 저장한다.

RVC는 third_party/rvc 에 클론하고 그 안의 .venv 에 의존성을 설치한 외부 저장소다
(third_party/README.md 참고). 추론 CLI 인자는 app/config.py의 RVC_INFER_ARGS,
학습 파라미터는 RVC_TRAIN_* 에서 관리한다.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from pathlib import Path

from app.config import (
    RVC_INFER_ARGS,
    RVC_PYTHON,
    RVC_REPO_DIR,
    RVC_TRAIN_BATCH_SIZE,
    RVC_TRAIN_EPOCHS,
    RVC_TRAIN_SAMPLE_RATE,
    RVC_TRAIN_SAVE_EVERY,
)
from app.engines.base import (
    EngineError,
    LogCallback,
    VoiceConversionEngine,
    run_engine_process,
)

# RVC 추론/학습에 필요한 사전 학습 가중치 (third_party/README.md 참고)
REQUIRED_INFER_ASSETS = (
    Path("assets/hubert_base/pytorch_model.bin"),
    Path("assets/rmvpe/rmvpe.pt"),
)
PRETRAINED_G = Path("assets/pretrained_v2/f0G40k.pth")
PRETRAINED_D = Path("assets/pretrained_v2/f0D40k.pth")


def _check_rvc_installed(extra_assets: tuple[Path, ...] = ()) -> tuple[bool, str]:
    script = RVC_REPO_DIR / "infer" / "cli.py"
    if not script.exists():
        return False, (
            f"RVC 저장소를 찾을 수 없습니다: {script}\n"
            "third_party/README.md 안내에 따라 저장소를 클론하세요."
        )
    if not RVC_PYTHON.exists():
        return False, (
            f"RVC 전용 가상환경이 없습니다: {RVC_PYTHON}\n"
            "third_party/README.md 안내에 따라 의존성을 설치하세요."
        )
    for asset in (*REQUIRED_INFER_ASSETS, *extra_assets):
        if not (RVC_REPO_DIR / asset).exists():
            return False, (
                f"RVC 사전 학습 가중치가 없습니다: {RVC_REPO_DIR / asset}\n"
                "third_party/README.md 안내에 따라 모델을 다운로드하세요."
            )
    return True, ""


class RVCEngine(VoiceConversionEngine):
    def __init__(self, model_path: Path, index_path: Path | None = None, pitch: int = 0):
        """model_path: 보이스 라이브러리에 저장된 .pth 체크포인트.
        index_path: 함께 저장된 .index 파일 (있으면 검색 품질 향상).
        pitch: 반음 단위 피치 이동 (예: 남→여 +12, 여→남 -12)."""
        self.model_path = model_path
        self.index_path = index_path
        self.pitch = pitch

    def is_ready(self) -> tuple[bool, str]:
        ok, msg = _check_rvc_installed()
        if not ok:
            return ok, msg
        if not self.model_path.exists():
            return False, f"모델 파일이 없습니다: {self.model_path}"
        return True, ""

    def convert(self, source_wav: Path, out_wav: Path) -> Path:
        ready, msg = self.is_ready()
        if not ready:
            raise EngineError(msg)

        out_wav.parent.mkdir(parents=True, exist_ok=True)
        values = {
            "model_path": str(self.model_path.resolve()),
            "source_wav": str(source_wav.resolve()),
            "out_wav": str(out_wav.resolve()),
            "pitch": str(self.pitch),
        }
        args = [a.format(**values) for a in RVC_INFER_ARGS]
        if self.index_path and self.index_path.exists():
            args += ["--index", str(self.index_path.resolve()), "--index-rate", "0.75"]
        else:
            args += ["--index-rate", "0"]
        run_engine_process(RVC_PYTHON, args, RVC_REPO_DIR, "RVC 변환")
        if not out_wav.exists():
            raise EngineError(f"RVC 변환 결과 파일이 생성되지 않았습니다: {out_wav}")
        return out_wav


@dataclass
class TrainResult:
    model_path: Path
    index_path: Path | None


def _write_filelist_and_config(exp_dir: Path, sr: str) -> None:
    """RVC WebUI의 run_train_model()과 동일하게 filelist.txt / config.json 을 만든다.

    (단일 화자, F0 사용, v2 기준. mute 샘플 2개를 섞어 무음 구간 학습을 돕는다.)
    """
    gt_dir = exp_dir / "0_gt_wavs"
    fea_dir = exp_dir / "3_feature768"
    f0_dir = exp_dir / "2a_f0"
    f0nsf_dir = exp_dir / "2b-f0nsf"

    def stems(d: Path) -> set[str]:
        return {p.name.split(".")[0] for p in d.iterdir()} if d.exists() else set()

    names = stems(gt_dir) & stems(fea_dir) & stems(f0_dir) & stems(f0nsf_dir)
    if not names:
        raise EngineError(f"학습에 쓸 수 있는 음성이 없습니다(전처리/특징 추출 결과 확인): {exp_dir}")

    def p(path: Path) -> str:
        return path.as_posix()

    lines = [
        f"{p(gt_dir / (n + '.wav'))}|{p(fea_dir / (n + '.npy'))}|"
        f"{p(f0_dir / (n + '.wav.npy'))}|{p(f0nsf_dir / (n + '.wav.npy'))}|0"
        for n in sorted(names)
    ]
    mute = RVC_REPO_DIR / "logs" / "mute"
    mute_line = (
        f"{p(mute / '0_gt_wavs' / f'mute{sr}.wav')}|{p(mute / '3_feature768' / 'mute.npy')}|"
        f"{p(mute / '2a_f0' / 'mute.wav.npy')}|{p(mute / '2b-f0nsf' / 'mute.wav.npy')}|0"
    )
    lines += [mute_line, mute_line]
    random.shuffle(lines)
    (exp_dir / "filelist.txt").write_text("\n".join(lines), encoding="utf-8")

    # WebUI 규칙: v2라도 40k는 configs/v1/40k.json 을 사용한다.
    config_rel = f"v1/{sr}.json" if sr == "40k" else f"v2/{sr}.json"
    config_data = json.loads((RVC_REPO_DIR / "configs" / config_rel).read_text(encoding="utf-8"))
    (exp_dir / "config.json").write_text(
        json.dumps(config_data, ensure_ascii=False, indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def train_rvc_voice(
    exp_name: str,
    dataset_dir: Path,
    epochs: int = RVC_TRAIN_EPOCHS,
    batch_size: int = RVC_TRAIN_BATCH_SIZE,
    on_log: LogCallback | None = None,
) -> TrainResult:
    """깨끗한 TTS 음성 샘플 폴더(dataset_dir)로부터 새 목소리를 1회 학습한다.

    RVC 공식 CLI 흐름(docs/en/cli.md)을 그대로 따른다:
    전처리 -> F0 추출(RMVPE, GPU) -> HuBERT 특징 추출 -> 모델 학습 -> 인덱스 학습.
    RTX 2070(VRAM 8GB) 기준 목소리당 수십 분 소요 예상.

    exp_name 은 ASCII만 사용할 것 (faiss 등 일부 네이티브 라이브러리가 비 ASCII
    파일명을 처리하지 못함).
    """
    ok, msg = _check_rvc_installed((PRETRAINED_G, PRETRAINED_D))
    if not ok:
        raise EngineError(msg)
    if not exp_name.isascii():
        raise EngineError(f"실험 이름은 영문/숫자만 사용하세요: {exp_name}")
    if not dataset_dir.is_dir() or not any(dataset_dir.iterdir()):
        raise EngineError(f"학습용 음성 데이터가 비어 있습니다: {dataset_dir}")

    sr = RVC_TRAIN_SAMPLE_RATE
    sr_hz = {"32k": 32000, "40k": 40000, "48k": 48000}[sr]
    n_cpu = str(max(1, min(os.cpu_count() or 1, 8)))
    exp_dir = RVC_REPO_DIR / "logs" / exp_name
    exp_dir.mkdir(parents=True, exist_ok=True)
    # WebUI는 시작 시 만들어 두지만 CLI 단독 실행 시에는 없어서 최종 저장이 실패한다.
    (RVC_REPO_DIR / "assets" / "weights").mkdir(parents=True, exist_ok=True)
    (RVC_REPO_DIR / "assets" / "indices").mkdir(parents=True, exist_ok=True)

    def step(label: str, args: list[str]) -> None:
        if on_log:
            on_log(f"== {label} ==")
        run_engine_process(RVC_PYTHON, args, RVC_REPO_DIR, f"RVC {label}", on_log)

    step("1/5 데이터 전처리", [
        "train/preprocess.py", str(dataset_dir.resolve()), str(sr_hz), n_cpu,
        str(exp_dir), "False", "3.7",
    ])
    step("2/5 F0 추출 (RMVPE)", [
        "train/dataset/extract_f0.py", "cuda", "1", "0", "0", str(exp_dir), "true",
    ])
    step("3/5 HuBERT 특징 추출", [
        "train/dataset/extract_hubert_feature.py", "cuda:0", "1", "0", "0",
        str(exp_dir), "v2", "true",
    ])
    _write_filelist_and_config(exp_dir, sr)
    step("4/5 모델 학습", [
        "train/train.py", "-e", exp_name, "-sr", sr, "-f0", "1",
        "-bs", str(batch_size), "-g", "0", "-te", str(epochs),
        "-se", str(min(RVC_TRAIN_SAVE_EVERY, epochs)),
        "-pg", PRETRAINED_G.as_posix(), "-pd", PRETRAINED_D.as_posix(),
        "-l", "1", "-c", "0", "-sw", "0", "-v", "v2",
    ])
    step("5/5 인덱스 학습", [
        "train/train_index.py", exp_name, "v2", "assets/indices", n_cpu, "single",
    ])

    model_path = RVC_REPO_DIR / "assets" / "weights" / f"{exp_name}.pth"
    if not model_path.exists():
        raise EngineError(f"학습은 끝났지만 모델 파일을 찾을 수 없습니다: {model_path}")
    indexes = sorted(exp_dir.glob("added_*.index"), key=lambda q: q.stat().st_mtime)
    return TrainResult(model_path=model_path, index_path=indexes[-1] if indexes else None)
