# AI 음성 변환 프로그램

좌측 영상/음성의 목소리를 우측에 올린 다수의 영상에 동일하게 입히는 Windows용
음성 변환 프로그램. 립싱크는 포함하지 않고 목소리 변환만 수행한다. 자세한 스펙은
개발 요청 문서(2026-09-25 작성)를 참고.

## 왜 이렇게 구성했는가 (git 관련 안내)

- 학습된 보이스 모델 파일(`.pth`, `.index`)과 `venv/`, `__pycache__/` 같은 폴더는
  용량이 크거나 재생성 가능하므로 `.gitignore`에 등록해 저장소에는 올라가지 않는다.
  **코드만 git에 올리고, 모델 파일은 로컬 PC에만 둔다.**
- `third_party/`(Seed-VC, RVC 저장소)도 사용자가 로컬에서 직접 클론하는 외부
  의존성이라 저장소에 포함하지 않는다.

## 프로젝트 구조

```
app/
  config.py            # 경로 설정 (exe 옆 data/ 폴더에 저장 — C드라이브 초기화 대비)
  main.py              # 진입점 (PySide6 GUI 실행)
  ui/main_window.py     # 좌측 타겟 목소리 / 우측 다중 영상 업로드 GUI
  pipeline/
    audio_pipeline.py   # ffmpeg 오디오 추출/구간 분할/재조립
    video_pipeline.py   # 비디오 트랙 복사 + 오디오 트랙 교체
    convert_job.py       # 영상 1개에 대한 전체 변환 오케스트레이션
  voice/
    library.py           # 보이스 라이브러리 메타데이터(JSON) 관리
    tagging.py            # F0 기반 성별 분류 + jitter/shimmer 톤 추천
  engines/
    seedvc_engine.py       # 제로샷 즉석 변환 (좌측 업로드)
    rvc_engine.py            # 사전 학습 모델 변환 + 학습 (좌측 라이브러리 선택)
scripts/train_voice.py     # 새 목소리 학습 + 라이브러리 등록 CLI
packaging/                  # PyInstaller 빌드 spec/스크립트
third_party/                 # Seed-VC, RVC 클론 위치 (gitignore, 로컬 전용)
data/                         # 보이스 라이브러리/모델/출력물 (gitignore, 로컬 전용)
tests/                         # pytest 단위 테스트
```

## 로컬 Windows 개발 환경 셋업

이 저장소는 컨테이너(Linux)에서 스캐폴딩했지만, 실제 학습/GPU 추론/exe 패키징은
**로컬 Windows PC(D드라이브 프로젝트 폴더)에서 Claude Code로 진행**하는 것을 전제로
한다. C드라이브가 재부팅 시 초기화되므로 프로젝트 폴더, 가상환경, 데이터 전부
D드라이브 등에 두어야 한다.

```powershell
# D드라이브에서 저장소 클론 (이미 이 폴더에 있다면 생략)
cd D:\
git clone <이 저장소 URL> voice-changer
cd voice-changer

# 앱(GUI) 가상환경 생성 — D드라이브의 Python 3.12 사용 (C드라이브 Python 금지)
D:\프로그램\Python\python.exe -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 외부 엔진 클론 + 엔진별 전용 가상환경 + 사전학습 가중치
# → third_party/README.md 의 명령을 그대로 실행

# ffmpeg: 프로젝트 루트 ffmpeg/ 폴더에 동봉 (gitignore 대상)
New-Item -ItemType Directory -Force ffmpeg | Out-Null
curl.exe -L -o ffmpeg\ffmpeg.exe https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/ffmpeg.exe
curl.exe -L -o ffmpeg\ffprobe.exe https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/ffprobe.exe
```

앱 venv에는 torch가 필요 없다. 음성 변환/학습은 각 엔진의 `.venv` python이 별도
프로세스로 수행한다.

## 실행

```powershell
python -m app.main
```

## 새 목소리 학습 (RVC)

```powershell
python scripts/train_voice.py --name "그록-남성1" --gender male --dataset "D:\tts_samples\grok_male1"
```

## exe 패키징

```powershell
python packaging/build.py
# 결과: dist/AI음성변환/AI음성변환.exe
```

## 테스트

외부 GPU/ffmpeg 의존 없이 돌아가는 단위 테스트(경로 설정, 보이스 라이브러리 CRUD,
태깅 로직)는 다음으로 실행:

```bash
pip install pytest numpy librosa
pytest tests/
```

## 주의: 외부 엔진 CLI 버전 차이

Seed-VC / RVC는 활발히 개발 중인 외부 프로젝트라 스크립트 인자가 버전마다 달라질
수 있다. 검증된 커밋은 `third_party/README.md`에 적어 두었다. 저장소를 업데이트해서
CLI가 바뀌면 `app/config.py`의 `SEEDVC_INFER_ARGS` / `RVC_INFER_ARGS` 와
`app/engines/rvc_engine.py`의 `train_rvc_voice()` 학습 단계를 맞춰 수정한다.
