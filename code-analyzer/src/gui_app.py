from __future__ import annotations

import io
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
    QTextEdit, QFrame, QScrollArea, QGridLayout,
)

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon, InfoBar, InfoBarPosition,
    PushButton, PrimaryPushButton, LineEdit, ComboBox, SwitchButton,
    CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel, TitleLabel,
    ProgressBar, IndeterminateProgressBar, TextEdit, ScrollArea,
    setTheme, Theme, setThemeColor, qconfig, FluentStyleSheet,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import (
    load_config,
    run_analysis,
    generate_reports,
    SUPPORTED_EXTENSIONS,
)


class AnalysisWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict, int, int, int)
    error_signal = pyqtSignal(str)

    def __init__(self, project_dir: str, config_file: str, use_llm: bool, gen_html: bool) -> None:
        super().__init__()
        self._project_dir = project_dir
        self._config_file = config_file
        self._use_llm = use_llm
        self._gen_html = gen_html

    def run(self) -> None:
        try:
            self._redirect_output()
            config = load_config(self._config_file)
            if not self._use_llm:
                config.setdefault("llm", {})["enabled"] = False
            if not self._gen_html:
                config.setdefault("output", {})["include_html"] = False

            graph = run_analysis(config, self._project_dir)
            node_count = len(graph.get_all_nodes())
            total_lines = sum(n.lines for n in graph.get_all_nodes())
            dep_count = sum(len(n.imports) for n in graph.get_all_nodes())
            paths = generate_reports(graph, config, self._project_dir)

            self._restore_output()
            self.finished_signal.emit(paths, node_count, total_lines, dep_count)
        except Exception as exc:
            self._restore_output()
            self.error_signal.emit(str(exc))

    def _redirect_output(self) -> None:
        sys.stdout = _LogRedirector(self.log_signal)
        sys.stderr = _LogRedirector(self.log_signal, prefix="[错误] ")

    def _restore_output(self) -> None:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


class _LogRedirector(io.StringIO):
    def __init__(self, signal: pyqtSignal, prefix: str = "") -> None:
        super().__init__()
        self._signal = signal
        self._prefix = prefix
        self._buffer: list[str] = []
        self._timer = QTimer()
        self._timer.timeout.connect(self._flush)
        self._timer.start(100)

    def write(self, s: str) -> int:
        if s.strip():
            self._buffer.append(self._prefix + s)
        return len(s)

    def _flush(self) -> None:
        while self._buffer:
            self._signal.emit(self._buffer.pop(0))

    def flush(self) -> None:
        self._flush()


class ConfigCard(CardWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setBorderRadius(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title_row = QHBoxLayout()
        StrongBodyLabel("分析配置", self)
        title_row.addWidget(StrongBodyLabel("分析配置", self))
        title_row.addStretch()
        layout.addLayout(title_row)

        grid = QGridLayout()
        grid.setSpacing(12)

        grid.addWidget(BodyLabel("项目目录", self), 0, 0)
        self._project_edit = LineEdit(self)
        self._project_edit.setPlaceholderText("选择要分析的项目根目录...")
        self._project_edit.setClearButtonEnabled(True)
        grid.addWidget(self._project_edit, 0, 1)
        btn = PushButton(FluentIcon.FOLDER, "选择", self)
        btn.clicked.connect(self._browse_folder)
        grid.addWidget(btn, 0, 2)

        grid.addWidget(BodyLabel("配置文件", self), 1, 0)
        self._config_edit = LineEdit(self)
        self._config_edit.setPlaceholderText("config.yaml 路径...")
        self._config_edit.setClearButtonEnabled(True)
        grid.addWidget(self._config_edit, 1, 1)
        btn2 = PushButton(FluentIcon.DOCUMENT, "选择", self)
        btn2.clicked.connect(self._browse_config)
        grid.addWidget(btn2, 1, 2)

        layout.addLayout(grid)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(24)
        self._llm_switch = SwitchButton(self)
        llm_label = QHBoxLayout()
        llm_label.setSpacing(8)
        llm_label.addWidget(self._llm_switch)
        llm_label.addWidget(BodyLabel("LLM 语义分析", self))
        opts_row.addLayout(llm_label)

        self._html_switch = SwitchButton(self)
        self._html_switch.setChecked(True)
        html_label = QHBoxLayout()
        html_label.setSpacing(8)
        html_label.addWidget(self._html_switch)
        html_label.addWidget(BodyLabel("HTML 可视化报告", self))
        opts_row.addLayout(html_label)
        opts_row.addStretch()
        layout.addLayout(opts_row)

    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if path:
            self._project_edit.setText(path.replace("/", "\\"))

    def _browse_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择配置文件", "", "YAML (*.yaml *.yml);;所有文件 (*)")
        if path:
            self._config_edit.setText(path.replace("/", "\\"))

    def get_project_path(self) -> str:
        return self._project_edit.text().strip()

    def get_config_path(self) -> str:
        return self._config_edit.text().strip()

    def set_project_path(self, path: str) -> None:
        self._project_edit.setText(path)

    def set_config_path(self, path: str) -> None:
        self._config_edit.setText(path)

    def is_llm_enabled(self) -> bool:
        return self._llm_switch.isChecked()

    def is_html_enabled(self) -> bool:
        return self._html_switch.isChecked()


class LogCard(CardWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setBorderRadius(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("运行日志", self))
        header.addStretch()
        layout.addLayout(header)

        self._log_area = QTextEdit(self)
        self._log_area.setReadOnly(True)
        self._log_area.setFont(QFont("Cascadia Code", 10))
        self._log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self._log_area)

    def append_log(self, text: str) -> None:
        self._log_area.moveCursor(QTextCursor.MoveOperation.End)
        color = "#cdd6f4"
        if text.startswith("[错误]"):
            color = "#ed8796"
        elif text.startswith("[警告]"):
            color = "#eed49f"
        elif text.startswith("[信息]"):
            color = "#7dc4e4"
        self._log_area.setTextColor(QColor(color))
        self._log_area.insertPlainText(text)
        scrollbar = self._log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self._log_area.clear()

    def set_light_theme(self) -> None:
        self._log_area.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 8px;
            }
        """)

    def set_dark_theme(self) -> None:
        self._log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                padding: 8px;
            }
        """)


class SummaryCard(CardWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setBorderRadius(8)
        self.setFixedHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)

        self._status_label = BodyLabel("就绪 — 选择项目目录后点击「开始分析」", self)
        layout.addWidget(self._status_label)
        layout.addStretch()

        self._stats_label = BodyLabel("", self)
        layout.addWidget(self._stats_label)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_stats(self, text: str) -> None:
        self._stats_label.setText(text)


class AnalyzerPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._html_path: str = ""
        self._output_dir: str = ""
        self._analyzing = False

        self._build_ui()
        self._auto_load_config()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        title = TitleLabel("Code Analyzer", self)
        layout.addWidget(title)
        layout.addWidget(BodyLabel("项目代码结构分析工具 — 自动梳理文件依赖关系与功能概览", self))

        layout.addSpacing(8)

        self._config_card = ConfigCard(self)
        layout.addWidget(self._config_card)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self._analyze_btn = PrimaryPushButton(FluentIcon.PLAY, "开始分析", self)
        self._analyze_btn.clicked.connect(self._start_analysis)
        action_row.addWidget(self._analyze_btn)

        self._html_btn = PushButton(FluentIcon.LINK, "打开 HTML 报告", self)
        self._html_btn.setEnabled(False)
        self._html_btn.clicked.connect(self._open_html)
        action_row.addWidget(self._html_btn)

        self._folder_btn = PushButton(FluentIcon.FOLDER, "打开输出目录", self)
        self._folder_btn.setEnabled(False)
        self._folder_btn.clicked.connect(self._open_output)
        action_row.addWidget(self._folder_btn)

        action_row.addStretch()

        self._progress = IndeterminateProgressBar(self)
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        action_row.addWidget(self._progress)
        layout.addLayout(action_row)

        self._log_card = LogCard(self)
        layout.addWidget(self._log_card, stretch=1)

        self._summary_card = SummaryCard(self)
        layout.addWidget(self._summary_card)

    def _auto_load_config(self) -> None:
        candidates = []
        is_frozen = getattr(sys, "frozen", False)

        if is_frozen:
            exe_dir = Path(sys.executable).parent
            local_config = exe_dir / "config.yaml"
            if local_config.exists():
                candidates.append(local_config)
            else:
                bundle_config = Path(sys._MEIPASS) / "config.yaml"
                if bundle_config.exists():
                    try:
                        import shutil
                        shutil.copy2(str(bundle_config), str(local_config))
                        candidates.append(local_config)
                    except OSError:
                        candidates.append(bundle_config)

        candidates.extend([
            Path.cwd() / "config.yaml",
            Path(__file__).resolve().parent.parent / "config.yaml",
        ])

        for candidate in candidates:
            if candidate.exists():
                self._config_card.set_config_path(str(candidate))
                break
        else:
            if is_frozen:
                self._config_card.set_config_path(str(Path(sys.executable).parent / "config.yaml"))
            else:
                self._config_card.set_config_path(str(Path.cwd() / "config.yaml"))

    def _start_analysis(self) -> None:
        project_dir = self._config_card.get_project_path()
        config_file = self._config_card.get_config_path()

        if not project_dir:
            InfoBar.warning("提示", "请先选择要分析的项目目录", duration=3000, parent=self, position=InfoBarPosition.TOP)
            return
        if not os.path.isdir(project_dir):
            InfoBar.error("错误", f"目录不存在: {project_dir}", duration=5000, parent=self, position=InfoBarPosition.TOP)
            return
        if not config_file or not os.path.isfile(config_file):
            InfoBar.error("错误", f"配置文件不存在: {config_file}", duration=5000, parent=self, position=InfoBarPosition.TOP)
            return

        self._analyzing = True
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("分析中...")
        self._html_btn.setEnabled(False)
        self._folder_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.start()
        self._log_card.clear()
        self._summary_card.set_status("正在分析...")
        self._summary_card.set_stats("")

        self._worker = AnalysisWorker(
            project_dir, config_file,
            self._config_card.is_llm_enabled(),
            self._config_card.is_html_enabled(),
        )
        self._worker.log_signal.connect(self._log_card.append_log)
        self._worker.finished_signal.connect(self._on_done)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _on_done(self, paths: dict, node_count: int, total_lines: int, dep_count: int) -> None:
        self._analyzing = False
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("开始分析")
        self._progress.stop()
        self._progress.setVisible(False)
        self._summary_card.set_status("分析完成")
        self._summary_card.set_stats(f"文件 {node_count}  ·  代码行 {total_lines}  ·  依赖 {dep_count}")

        self._log_card.append_log("\n" + "─" * 48 + "\n")
        self._log_card.append_log("  分析完成\n")
        self._log_card.append_log("─" * 48 + "\n")
        self._log_card.append_log(f"  文件数       {node_count}\n")
        self._log_card.append_log(f"  代码行数     {total_lines}\n")
        self._log_card.append_log(f"  依赖关系     {dep_count}\n")
        self._log_card.append_log("─" * 48 + "\n")

        html_path = paths.get("html", "")
        if html_path and os.path.isfile(html_path):
            self._html_path = html_path
            self._html_btn.setEnabled(True)

        output_dir = paths.get("output_dir", "")
        if output_dir:
            self._output_dir = output_dir
            self._folder_btn.setEnabled(True)

        InfoBar.success("完成", f"成功分析 {node_count} 个文件", duration=3000, parent=self, position=InfoBarPosition.TOP)

    def _on_error(self, error_msg: str) -> None:
        self._analyzing = False
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("开始分析")
        self._progress.stop()
        self._progress.setVisible(False)
        self._summary_card.set_status("分析失败")
        self._log_card.append_log(f"\n[错误] {error_msg}\n")
        InfoBar.error("错误", error_msg, duration=5000, parent=self, position=InfoBarPosition.TOP)

    def _open_html(self) -> None:
        if self._html_path and os.path.isfile(self._html_path):
            os.startfile(self._html_path)

    def _open_output(self) -> None:
        if self._output_dir and os.path.isdir(self._output_dir):
            os.startfile(self._output_dir)
        else:
            project_dir = self._config_card.get_project_path()
            output_dir = str(Path(project_dir or ".") / "output")
            if os.path.isdir(output_dir):
                os.startfile(output_dir)
            elif os.path.isdir(os.path.dirname(output_dir)):
                os.startfile(os.path.dirname(output_dir))


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        layout.addWidget(TitleLabel("设置", self))
        layout.addWidget(BodyLabel("管理应用配置与主题", self))
        layout.addSpacing(8)

        card = CardWidget(self)
        card.setBorderRadius(8)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        card_layout.addWidget(StrongBodyLabel("主题设置", self))

        theme_row = QHBoxLayout()
        theme_row.addWidget(BodyLabel("应用主题", self))
        theme_row.addStretch()
        self._theme_combo = ComboBox(self)
        self._theme_combo.addItems(["深色", "浅色", "跟随系统"])
        self._theme_combo.setCurrentIndex(0)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo)
        card_layout.addLayout(theme_row)

        card_layout.addWidget(StrongBodyLabel("支持的语言", self))
        lang_grid = QGridLayout()
        lang_grid.setSpacing(8)
        langs = [
            ("Python", ".py"),
            ("JavaScript", ".js/.jsx/.mjs/.cjs"),
            ("TypeScript", ".ts/.tsx"),
            ("Go", ".go"),
            ("Rust", ".rs"),
            ("Java", ".java"),
            ("PHP", ".php"),
        ]
        for i, (name, ext) in enumerate(langs):
            lang_grid.addWidget(BodyLabel(name, self), i // 2, (i % 2) * 2)
            lang_grid.addWidget(BodyLabel(ext, self), i // 2, (i % 2) * 2 + 1)
        card_layout.addLayout(lang_grid)

        layout.addWidget(card)
        layout.addStretch()

    def _on_theme_changed(self, index: int) -> None:
        if index == 0:
            setTheme(Theme.DARK)
        elif index == 1:
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.AUTO)


class MainWindow(FluentWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Code Analyzer")
        self.resize(1000, 720)
        self.setMinimumSize(800, 600)

        setTheme(Theme.DARK)
        setThemeColor("#0078d4")

        self._analyzer_page = AnalyzerPage(self)
        self._settings_page = SettingsPage(self)

        self.addSubInterface(self._analyzer_page, FluentIcon.HOME, "分析")
        self.addSubInterface(self._settings_page, FluentIcon.SETTING, "设置", NavigationItemPosition.BOTTOM)

        self.navigationInterface.setCurrentItem("分析")

        self._apply_log_theme()

    def _apply_log_theme(self) -> None:
        self._analyzer_page._log_card.set_dark_theme()


def main() -> None:
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI Variable", 10))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()