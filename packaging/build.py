"""로컬 Windows PC에서 exe 패키징을 실행하는 헬퍼 스크립트.

사용법 (프로젝트 루트, 가상환경 활성화 상태에서):
    python packaging/build.py

빌드 결과는 dist/AI음성변환/ 폴더에 생성된다. ffmpeg.exe를 오프라인으로
동봉하려면 빌드 후 dist/AI음성변환/ffmpeg/ffmpeg.exe 로 복사해두면
app.config.resolve_ffmpeg_bin()이 자동으로 이를 사용한다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    spec_path = PROJECT_ROOT / "packaging" / "build_exe.spec"
    cmd = [sys.executable, "-m", "PyInstaller", str(spec_path), "--noconfirm"]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
