from app.voice.library import VoiceLibrary


def test_add_and_list_by_gender(tmp_path):
    lib = VoiceLibrary(db_path=tmp_path / "library.json")
    entry = lib.add(name="테스트남성1", gender="male", model_path="models/test.pth")

    males = lib.list_by_gender("male")
    assert len(males) == 1
    assert males[0].id == entry.id
    assert lib.list_by_gender("female") == []


def test_update_tags_marks_user_edited(tmp_path):
    lib = VoiceLibrary(db_path=tmp_path / "library.json")
    entry = lib.add(name="원래이름", gender="female", model_path="models/x.pth")

    updated = lib.update_tags(entry.id, name="수정된이름", tone_tags=["허스키함"])

    assert updated.name == "수정된이름"
    assert updated.tone_tags == ["허스키함"]
    assert updated.tag_source == "user_edited"


def test_persists_across_reload(tmp_path):
    db_path = tmp_path / "library.json"
    lib1 = VoiceLibrary(db_path=db_path)
    lib1.add(name="영구저장테스트", gender="male", model_path="models/y.pth")

    lib2 = VoiceLibrary(db_path=db_path)
    assert len(lib2.list_all()) == 1
    assert lib2.list_all()[0].name == "영구저장테스트"
