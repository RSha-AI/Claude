# third_party

이 폴더에는 용량이 큰 외부 음성 변환 엔진 저장소를 **로컬에 직접 클론**해서 둡니다.
(깃허브에는 올라가지 않도록 `.gitignore`에서 이 폴더 전체를 제외했습니다.)

```bash
# 프로젝트 루트에서 실행
git clone https://github.com/Plachtaa/seed-vc.git third_party/seed-vc
git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git third_party/rvc
```

`app/engines/seedvc_engine.py` 와 `app/engines/rvc_engine.py` 는 위 경로(`third_party/seed-vc`,
`third_party/rvc`)에 저장소가 있다고 가정하고 동작합니다. 다른 경로에 두었다면
`app/config.py` 의 `SEEDVC_REPO_DIR`, `RVC_REPO_DIR` 값을 수정하세요.
