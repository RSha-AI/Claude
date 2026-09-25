"""메인 GUI.

좌측: 타겟 목소리 지정 (업로드 = 제로샷 즉석 변환 / 드롭다운 선택 = 학습된 라이브러리)
우측: 변환 대상 영상 다수 업로드, 영상별 구간(시작~종료 초) 지정
하단: 일괄 변환 실행 + 진행률 표시
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import OUTPUT_DIR, ensure_data_dirs
from app.engines.base import VoiceConversionEngine
from app.engines.rvc_engine import RVCEngine
from app.engines.seedvc_engine import SeedVCEngine
from app.pipeline.convert_job import ConvertRequest, convert_one_video
from app.voice.library import VoiceLibrary


@dataclass
class VideoTask:
    path: Path
    start_edit: QLineEdit
    end_edit: QLineEdit

    def start_sec(self) -> float | None:
        text = self.start_edit.text().strip()
        return float(text) if text else None

    def end_sec(self) -> float | None:
        text = self.end_edit.text().strip()
        return float(text) if text else None


class ConversionWorker(QThread):
    progress = Signal(str, str)  # (video_name, status_text)
    finished_all = Signal()
    failed = Signal(str, str)  # (video_name, error_message)

    def __init__(self, tasks: list[VideoTask], engine: VoiceConversionEngine):
        super().__init__()
        self.tasks = tasks
        self.engine = engine

    def run(self) -> None:
        for task in self.tasks:
            name = task.path.name
            out_path = OUTPUT_DIR / f"converted_{task.path.stem}.mp4"
            try:
                convert_one_video(
                    ConvertRequest(
                        video_path=task.path,
                        out_video_path=out_path,
                        start_sec=task.start_sec(),
                        end_sec=task.end_sec(),
                    ),
                    self.engine,
                    on_progress=lambda msg, n=name: self.progress.emit(n, msg),
                )
            except Exception as exc:  # noqa: BLE001 - 사용자에게 그대로 사유 표시
                self.failed.emit(name, str(exc))
        self.finished_all.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_data_dirs()
        self.setWindowTitle("AI 음성 변환")
        self.resize(900, 600)

        self.library = VoiceLibrary()
        self.reference_wav: Path | None = None
        self.video_tasks: list[VideoTask] = []
        self.worker: ConversionWorker | None = None

        container = QWidget()
        self.setCentralWidget(container)
        outer = QVBoxLayout(container)

        panels_row = QHBoxLayout()
        panels_row.addWidget(self._build_left_panel(), 1)
        panels_row.addWidget(self._build_right_panel(), 2)
        outer.addLayout(panels_row)

        self.convert_btn = QPushButton("변환 시작")
        self.convert_btn.clicked.connect(self.on_convert_clicked)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("")
        outer.addWidget(self.convert_btn)
        outer.addWidget(self.progress_bar)
        outer.addWidget(self.status_label)

    # --- 좌측: 타겟 목소리 -------------------------------------------------
    def _build_left_panel(self) -> QGroupBox:
        box = QGroupBox("타겟 목소리 (좌측)")
        layout = QVBoxLayout(box)

        upload_row = QHBoxLayout()
        self.upload_label = QLabel("업로드 없음 (아래 라이브러리 사용)")
        upload_btn = QPushButton("영상/음성 업로드 (제로샷)")
        upload_btn.clicked.connect(self.on_upload_reference)
        upload_row.addWidget(upload_btn)
        layout.addLayout(upload_row)
        layout.addWidget(self.upload_label)

        layout.addWidget(QLabel("또는 학습된 보이스 라이브러리 선택:"))

        gender_row = QHBoxLayout()
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["male", "female"])
        self.gender_combo.currentTextChanged.connect(self.refresh_voice_combo)
        gender_row.addWidget(QLabel("성별"))
        gender_row.addWidget(self.gender_combo)
        layout.addLayout(gender_row)

        voice_row = QHBoxLayout()
        self.voice_combo = QComboBox()
        edit_btn = QPushButton("✏")
        edit_btn.setToolTip("자동 태그(이름/메모/성별/톤) 수정")
        edit_btn.clicked.connect(self.on_edit_voice)
        voice_row.addWidget(self.voice_combo)
        voice_row.addWidget(edit_btn)
        layout.addLayout(voice_row)

        self.refresh_voice_combo()
        layout.addStretch(1)
        return box

    def refresh_voice_combo(self) -> None:
        self.voice_combo.clear()
        gender = self.gender_combo.currentText()
        for entry in self.library.list_by_gender(gender):
            label = entry.name
            if entry.tone_tags:
                label += f" ({', '.join(entry.tone_tags)})"
            self.voice_combo.addItem(label, entry.id)

    def on_upload_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "레퍼런스 영상/음성 선택", "", "Media Files (*.mp4 *.mov *.mkv *.wav *.mp3)"
        )
        if path:
            self.reference_wav = Path(path)
            self.upload_label.setText(f"업로드됨: {self.reference_wav.name}")

    def on_edit_voice(self) -> None:
        voice_id = self.voice_combo.currentData()
        if not voice_id:
            return
        entry = self.library.get(voice_id)
        if not entry:
            return
        new_name, ok = QInputDialog.getText(self, "이름 수정", "이름:", text=entry.name)
        if not ok:
            return
        new_memo, ok = QInputDialog.getText(self, "메모 수정", "메모:", text=entry.memo)
        if not ok:
            return
        self.library.update_tags(voice_id, name=new_name, memo=new_memo)
        self.refresh_voice_combo()

    # --- 우측: 변환 대상 영상 -----------------------------------------------
    def _build_right_panel(self) -> QGroupBox:
        box = QGroupBox("변환 대상 영상 (우측)")
        layout = QVBoxLayout(box)

        add_btn = QPushButton("영상 추가 (다중 선택 가능)")
        add_btn.clicked.connect(self.on_add_videos)
        layout.addWidget(add_btn)

        self.video_list = QListWidget()
        layout.addWidget(self.video_list)
        return box

    def on_add_videos(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "영상 선택", "", "Video Files (*.mp4 *.mov *.mkv *.avi)"
        )
        for p in paths:
            self._add_video_row(Path(p))

    def _add_video_row(self, path: Path) -> None:
        item_widget = QWidget()
        row = QHBoxLayout(item_widget)
        row.addWidget(QLabel(path.name), 2)
        row.addWidget(QLabel("시작(초)"))
        start_edit = QLineEdit()
        start_edit.setPlaceholderText("미입력=전체")
        row.addWidget(start_edit)
        row.addWidget(QLabel("종료(초)"))
        end_edit = QLineEdit()
        end_edit.setPlaceholderText("미입력=끝까지")
        row.addWidget(end_edit)

        list_item = QListWidgetItem(self.video_list)
        list_item.setSizeHint(item_widget.sizeHint())
        self.video_list.addItem(list_item)
        self.video_list.setItemWidget(list_item, item_widget)

        self.video_tasks.append(VideoTask(path=path, start_edit=start_edit, end_edit=end_edit))

    # --- 변환 실행 -----------------------------------------------------------
    def _build_engine(self) -> VoiceConversionEngine | None:
        if self.reference_wav is not None:
            return SeedVCEngine(self.reference_wav)

        voice_id = self.voice_combo.currentData()
        if not voice_id:
            QMessageBox.warning(self, "타겟 없음", "레퍼런스를 업로드하거나 라이브러리에서 선택하세요.")
            return None
        entry = self.library.get(voice_id)
        if not entry:
            return None
        return RVCEngine(Path(entry.model_path), Path(entry.index_path) if entry.index_path else None)

    def on_convert_clicked(self) -> None:
        if not self.video_tasks:
            QMessageBox.warning(self, "영상 없음", "변환할 영상을 먼저 추가하세요.")
            return
        engine = self._build_engine()
        if engine is None:
            return

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.worker = ConversionWorker(list(self.video_tasks), engine)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.failed.connect(self.on_worker_failed)
        self.worker.finished_all.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, video_name: str, status: str) -> None:
        self.status_label.setText(f"[{video_name}] {status}")

    def on_worker_failed(self, video_name: str, error: str) -> None:
        self.status_label.setText(f"[{video_name}] 실패: {error}")

    def on_worker_finished(self) -> None:
        self.convert_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"모든 작업 완료. 결과물 위치: {OUTPUT_DIR}")
