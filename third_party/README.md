# third_party

이 폴더에는 용량이 큰 외부 음성 변환 엔진 저장소를 **로컬에 직접 클론**해서 둡니다.
(깃허브에는 올라가지 않도록 `.gitignore`에서 이 폴더 전체를 제외했습니다.)

두 엔진은 torch / transformers / gradio 버전 요구가 서로 충돌하므로 **각 저장소 안에
전용 가상환경(`.venv`)을 따로 만든다.** 앱은 `app/config.py`의 `SEEDVC_PYTHON`,
`RVC_PYTHON`(= 각 저장소의 `.venv` python)으로 엔진을 별도 프로세스로 실행한다.

Python은 **3.12 x64**, 경로는 C드라이브가 아닌 곳(D드라이브 등)에 설치된 것을 사용한다.
아래는 RTX 2070 + NVIDIA 드라이버 546 (CUDA 12.3까지 지원) 기준.

```powershell
# 프로젝트 루트에서 실행. $PY 는 D드라이브에 설치한 Python 3.12
$PY = "D:\프로그램\Python\python.exe"

git clone https://github.com/Plachtaa/seed-vc.git third_party/seed-vc
git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git third_party/rvc

# --- Seed-VC (torch 2.4.0 + cu121) ---
& $PY -m venv third_party\seed-vc\.venv
$S = "third_party\seed-vc\.venv\Scripts\python.exe"
& $S -m pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu121
# 추론에 필요한 것만 설치 (requirements.txt의 gradio/funasr/modelscope/resemblyzer 등은
# 웹UI·평가 전용이라 제외. resemblyzer는 Windows에서 C 컴파일러가 필요해 실패하기도 함)
& $S -m pip install scipy==1.13.1 librosa==0.10.2 "huggingface-hub>=0.28.1" munch==4.0.0 einops==0.8.0 `
    descript-audio-codec==1.0.0 pydub==0.25.1 transformers==4.46.3 soundfile==0.12.1 numpy==1.26.4 `
    hydra-core==1.3.2 pyyaml python-dotenv accelerate
# 모델 가중치는 첫 변환 시 third_party/seed-vc/checkpoints/ 로 자동 다운로드된다.

# --- RVC (torch 2.7.1 + cu118; 저장소 README의 "RTX 50 이전" 경로) ---
& $PY -m venv third_party\rvc\.venv
$R = "third_party\rvc\.venv\Scripts\python.exe"
& $R -m pip install --upgrade pip "setuptools<81" wheel
& $R -m pip install torch==2.7.1+cu118 torchaudio==2.7.1+cu118 --index-url https://download.pytorch.org/whl/cu118 --extra-index-url https://pypi.org/simple
& $R -m pip install -r third_party\rvc\requirments_cu118_py312.txt --index-url https://pypi.org/simple

# RVC 사전 학습 가중치 (추론: hubert + rmvpe, 학습: pretrained_v2 40k + mute)
$HF = "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main"
$A = "third_party\rvc\assets"
New-Item -ItemType Directory -Force "$A\hubert_base","$A\rmvpe","$A\pretrained_v2" | Out-Null
foreach ($f in "config.json","preprocessor_config.json","pytorch_model.bin") { curl.exe -L -o "$A\hubert_base\$f" "$HF/hubert_base/$f" }
curl.exe -L -o "$A\rmvpe\rmvpe.pt" "$HF/rmvpe.pt"
curl.exe -L -o "$A\pretrained_v2\f0G40k.pth" "$HF/pretrained_v2/f0G40k.pth"
curl.exe -L -o "$A\pretrained_v2\f0D40k.pth" "$HF/pretrained_v2/f0D40k.pth"
curl.exe -L -o mute.zip "$HF/mute.zip"; & $R -m zipfile -e mute.zip third_party\rvc\logs; Remove-Item mute.zip
```

RVC 저장소의 원래 파일명은 `requirments_...txt`(오타 그대로)이다.

`app/engines/seedvc_engine.py` 와 `app/engines/rvc_engine.py` 는 위 경로(`third_party/seed-vc`,
`third_party/rvc`)에 저장소가 있다고 가정하고 동작합니다. 다른 경로에 두었다면
`app/config.py` 의 `SEEDVC_REPO_DIR`, `RVC_REPO_DIR` 값을 수정하세요.

## 검증된 버전

| 저장소 | 커밋 | 비고 |
| --- | --- | --- |
| seed-vc | `51383ef` (2025-04-20) | `inference.py` CLI 사용 |
| RVC WebUI | `81eed5e` (2026-08-04) | `infer/cli.py` 추론, `train/*.py` 5단계 학습 |
