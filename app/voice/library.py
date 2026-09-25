"""학습된 보이스 라이브러리 메타데이터 관리.

실제 모델 파일(.pth, .index)은 app.config.MODELS_DIR 아래에 저장되고,
이 모듈은 각 보이스에 대한 메타데이터(이름, 메모, 성별/톤 태그, 파일 경로)만
JSON으로 관리한다. .pth/.index 파일 자체는 절대 git에 커밋하지 않는다.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import VOICE_LIBRARY_DB, ensure_data_dirs


@dataclass
class VoiceEntry:
    id: str
    name: str
    gender: str  # "male" | "female" | "unknown"
    tone_tags: list[str] = field(default_factory=list)
    memo: str = ""
    model_path: str = ""  # .pth 경로 (상대 또는 절대)
    index_path: str = ""  # .index 경로
    mean_f0_hz: float = 0.0
    tag_source: str = "auto"  # "auto" | "user_edited"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceEntry":
        return cls(**data)


class VoiceLibrary:
    """보이스 라이브러리 JSON 저장소에 대한 얇은 CRUD 래퍼."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or VOICE_LIBRARY_DB
        self._entries: dict[str, VoiceEntry] = {}
        self._load()

    def _load(self) -> None:
        ensure_data_dirs()
        if not self.db_path.exists():
            self._entries = {}
            return
        raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        self._entries = {e["id"]: VoiceEntry.from_dict(e) for e in raw}

    def _save(self) -> None:
        ensure_data_dirs()
        data = [e.to_dict() for e in self._entries.values()]
        self.db_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(
        self,
        name: str,
        gender: str,
        model_path: str,
        index_path: str = "",
        tone_tags: list[str] | None = None,
        memo: str = "",
        mean_f0_hz: float = 0.0,
        tag_source: str = "auto",
    ) -> VoiceEntry:
        entry = VoiceEntry(
            id=str(uuid.uuid4()),
            name=name,
            gender=gender,
            tone_tags=tone_tags or [],
            memo=memo,
            model_path=model_path,
            index_path=index_path,
            mean_f0_hz=mean_f0_hz,
            tag_source=tag_source,
        )
        self._entries[entry.id] = entry
        self._save()
        return entry

    def update_tags(
        self,
        voice_id: str,
        *,
        name: str | None = None,
        gender: str | None = None,
        tone_tags: list[str] | None = None,
        memo: str | None = None,
    ) -> VoiceEntry:
        """드롭다운 옆 편집(연필) 버튼에서 사용자가 자동 태그를 직접 수정할 때 호출."""
        entry = self._entries[voice_id]
        if name is not None:
            entry.name = name
        if gender is not None:
            entry.gender = gender
        if tone_tags is not None:
            entry.tone_tags = tone_tags
        if memo is not None:
            entry.memo = memo
        entry.tag_source = "user_edited"
        self._save()
        return entry

    def remove(self, voice_id: str) -> None:
        self._entries.pop(voice_id, None)
        self._save()

    def get(self, voice_id: str) -> VoiceEntry | None:
        return self._entries.get(voice_id)

    def list_all(self) -> list[VoiceEntry]:
        return list(self._entries.values())

    def list_by_gender(self, gender: str) -> list[VoiceEntry]:
        return [e for e in self._entries.values() if e.gender == gender]
