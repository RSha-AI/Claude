from pathlib import Path

from app.config import BASE_DIR, DATA_DIR, MODELS_DIR, VOICE_LIBRARY_DIR, get_base_dir


def test_base_dir_is_project_root_in_dev_mode():
    # 개발 모드(스크립트 실행)에서는 sys.frozen이 없으므로 프로젝트 루트를 반환해야 한다.
    assert get_base_dir() == BASE_DIR
    assert (BASE_DIR / "app").is_dir()


def test_data_dirs_are_under_base_dir_not_home_or_appdata():
    # 요구사항: C드라이브(AppData 등)가 아니라 exe(또는 프로젝트) 기준 폴더에 저장.
    for d in (DATA_DIR, VOICE_LIBRARY_DIR, MODELS_DIR):
        assert Path(d).is_relative_to(BASE_DIR)
