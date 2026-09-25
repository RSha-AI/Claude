# PyInstaller spec 파일.
# 실행: pyinstaller packaging/build_exe.spec  (프로젝트 루트에서)
#
# --onedir(폴더 배포)를 기본으로 한다. torch 등 ML 라이브러리 포함으로 용량이
# 수백MB~수GB에 이르므로, onefile보다 onedir이 실행 속도/디버깅 면에서 유리하다.
# 더블클릭 실행 자체는 onedir 폴더 안의 AI음성변환.exe로도 동일하게 가능하다.
# 굳이 단일 파일이 필요하면 EXE(...) 호출 시 --onefile 옵션을 켜면 된다
# (COLLECT 단계를 생략하고 EXE에 binaries/datas를 직접 전달).

import sys
from pathlib import Path

block_cipher = None
PROJECT_ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "app" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "torch",
        "torchaudio",
        "librosa",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI음성변환",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="AI음성변환",
)
