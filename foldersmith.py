import sys
import os
import re
import shutil
import zipfile
from datetime import datetime

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows platforms
    winsound = None

from PyQt6.QtCore import (
    Qt,
    QSize,
    QPropertyAnimation,
    QEasingCurve,
    QThread,
    pyqtSignal,
    QParallelAnimationGroup,
    QPoint,
)
from PyQt6.QtGui import (
    QFont,
    QIcon,
    QColor,
    QPalette,
    QTextCharFormat,
    QSyntaxHighlighter,
    QAction,
    QGuiApplication,
    QCursor,
    QPixmap,
    QPainter,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QPushButton,
    QCheckBox,
    QComboBox,
    QLabel,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QFileDialog,
    QMessageBox,
    QMenuBar,
    QStatusBar,
    QMenu,
    QStyleFactory,
    QDialog,
    QFrame,
    QSizePolicy,
    QGraphicsOpacityEffect,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


def beep(freq, duration):
    """Play a beep if winsound is available (Windows only); never crash."""
    if winsound is None:
        return
    try:
        winsound.Beep(freq, duration)
    except Exception:
        pass


def get_asset_path(filename):
    """Get absolute path to assets, works for dev and for PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_path, "assets")
    path = os.path.join(assets_dir, filename)
    return path


#come back here later
# Color palette
#
# Comments always render in a muted italic green - a hue no file type ever
# uses - so a comment can never be mistaken for a file's own color. Every
# extension gets its own distinct color; unmatched extensions and dotfiles
# (.gitignore, .env, ...) get their own dedicated colors too, instead of
# silently falling back to a shade close to the comment color.
COMMENT_COLOR = "#6A9955"

FILE_COLORS_DARK = {
    ".py": "#4FC3F7", ".pyw": "#4FC3F7",
    ".js": "#FFCA28", ".jsx": "#FFCA28", ".ts": "#4FC3F7", ".tsx": "#4FC3F7",
    ".md": "#FFA726", ".markdown": "#FFA726",
    ".html": "#F06292", ".htm": "#F06292", ".xml": "#F06292",
    ".css": "#4DB6AC", ".scss": "#4DB6AC", ".less": "#4DB6AC",
    ".json": "#A1887F", ".yml": "#BA68C8", ".yaml": "#BA68C8",
    ".txt": "#4DD0E1", ".csv": "#4DD0E1", ".log": "#4DD0E1",
    ".sh": "#81C784", ".bat": "#81C784", ".ps1": "#81C784", ".sql": "#81C784",
    ".java": "#EF9A9A", ".c": "#90CAF9", ".cpp": "#90CAF9", ".h": "#90CAF9",
    ".go": "#4DD0E1", ".rs": "#FFAB91", ".php": "#B39DDB", ".rb": "#EF9A9A",
    ".png": "#CE93D8", ".jpg": "#CE93D8", ".jpeg": "#CE93D8", ".svg": "#CE93D8",
    ".ico": "#CE93D8", ".gif": "#CE93D8",
}
DOTFILE_COLOR_DARK = "#FFD54F"
GENERIC_FILE_COLOR_DARK = "#CFD8DC"
FOLDER_COLORS_DARK = ["#66BB6A", "#42A5F5", "#FFA726", "#AB47BC"]


def get_file_color(name):
    """Return a stable, distinct color for a file name - never the comment color."""
    if name.startswith(".") and name.count(".") == 1:
        return DOTFILE_COLOR_DARK
    ext = os.path.splitext(name)[1].lower()
    if ext in FILE_COLORS_DARK:
        return FILE_COLORS_DARK[ext]
    return GENERIC_FILE_COLOR_DARK


def get_folder_color(depth):
    return FOLDER_COLORS_DARK[min(max(depth, 0), len(FOLDER_COLORS_DARK) - 1)]


def make_emoji_icon(emoji, size=28):
    """Render an emoji onto a transparent pixmap so buttons always show an
    icon, regardless of platform (QIcon.fromTheme is unreliable on Windows,
    where no XDG icon theme is installed)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Segoe UI Emoji")
    font.setPixelSize(int(size * 0.72))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), emoji)
    painter.end()
    return QIcon(pixmap)


#come back here later
# Structure parsing - the ONE place that turns pasted text into a tree.
#
# Both the live preview and the actual folder/file creation now call this
# same function, so they can never disagree with each other again.
class Node:
    __slots__ = ("name", "is_folder", "depth", "comment", "children", "line_no", "closing", "parent")

    def __init__(self, name, is_folder, depth, comment=None, line_no=0, closing=False):
        self.name = name
        self.is_folder = is_folder
        self.depth = depth
        self.comment = comment
        self.children = []
        self.line_no = line_no
        self.closing = closing  # declared with a tree-diagram "└" connector
        self.parent = None


# Comment styles supported. Matched left-to-right across the whole line;
# whichever pattern matches earliest in the line wins, so e.g. a "#" inside
# a later "/* */" block doesn't get treated as a separate comment.
_COMMENT_PATTERNS = [
    re.compile(r"/\*.*?\*/"),        # C / CSS / JS block comments
    re.compile(r"<!--.*?-->"),       # HTML / XML
    re.compile(r"//.*$"),            # C, JS, Go, Rust, Java...
    re.compile(r"#.*$"),             # Python, shell, YAML...
    re.compile(r"(?<!\w)--.*$"),     # SQL, Lua, Haskell
    re.compile(r"(?<![\w.]);.*$"),   # INI, Lisp, Assembly
    re.compile(r"(?<!\w)%.*$"),      # LaTeX, Erlang, MATLAB
]


def strip_comment(line):
    """Remove the first (leftmost) comment found on the line. Returns
    (content_without_comment, comment_text_or_None)."""
    best = None
    for rx in _COMMENT_PATTERNS:
        m = rx.search(line)
        if m and (best is None or m.start() < best.start()):
            best = m
    if best is None:
        return line, None
    return line[: best.start()].rstrip(), best.group(0).strip()


def parse_structure(text):
    """Parse pasted folder-structure text (plain-indented or ASCII tree
    diagram) into a tree of Node objects, rooted at a synthetic empty root.

    Depth is computed primarily from tree-diagram connector characters
    (│ ├ └), since those survive most copy/paste pipelines better than
    literal spaces do; plain-indented input falls back to leading spaces,
    using the smallest observed indent as one level.
    """
    lines = text.split("\n")

    plain_indents = []
    for l in lines:
        if not l.strip() or any(c in l for c in "│├└"):
            continue
        lead = len(l) - len(l.lstrip(" "))
        if lead > 0:
            plain_indents.append(lead)
    indent_unit = min(plain_indents) if plain_indents else 4

    root = Node(name="", is_folder=True, depth=-1)
    stack = [root]

    for line_no, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue

        prefix_match = re.match(r"^([│├└─\s]*)", raw)
        prefix = prefix_match.group(1)
        sym_count = sum(prefix.count(c) for c in "│├└")
        connector = None
        for ch in prefix:
            if ch in "├└":
                connector = ch

        if sym_count > 0:
            depth = sym_count
        else:
            lead = len(raw) - len(raw.lstrip(" "))
            depth = lead // indent_unit if indent_unit else 0

        stripped = re.sub(r"[│├└─]", "", raw).strip()
        content, comment = strip_comment(stripped)
        content = content.strip()
        if not content:
            continue

        is_folder = content.endswith("/")
        name = content[:-1].strip() if is_folder else content
        if not name:
            continue

        top = stack[-1]
        # A folder declared with a closing "└" connector cannot have a
        # sibling at the same tree-diagram depth ("└" means "last item at
        # this level"). If the input's whitespace got collapsed (common
        # when pasting through chat apps or browsers, which flatten runs
        # of spaces to one) the next item can look like it's at the same
        # depth when it was really meant to nest under that folder - so
        # treat it as a child instead of guessing wrong the other way.
        if top is not root and top.closing and depth == top.depth:
            depth = top.depth + 1

        while len(stack) > 1 and stack[-1].depth >= depth:
            stack.pop()

        node = Node(
            name=name,
            is_folder=is_folder,
            depth=depth,
            comment=comment,
            line_no=line_no,
            closing=(connector == "└"),
        )
        node.parent = stack[-1]
        stack[-1].children.append(node)

        if is_folder:
            stack.append(node)

    return root, indent_unit


def compute_stats(root):
    """Folders / files / comments implied by a parsed tree - used by both
    Simulate and Create so their numbers can never diverge."""
    folders = files = comments = 0

    def walk(node):
        nonlocal folders, files, comments
        for child in node.children:
            if child.is_folder:
                folders += 1
            else:
                files += 1
            if child.comment:
                comments += 1
            walk(child)

    walk(root)
    return folders, files, comments


def count_nodes(node):
    total = 0
    for child in node.children:
        total += 1
        if child.is_folder:
            total += count_nodes(child)
    return total


def verify_on_disk(root_path, root_node):
    """Cross-check: walk the parsed tree and confirm every expected path
    really exists on disk. Returns a list of any paths that are missing."""
    missing = []

    def walk(node, path):
        for child in node.children:
            child_path = os.path.join(path, child.name)
            if child.is_folder:
                if not os.path.isdir(child_path):
                    missing.append(child_path)
                walk(child, child_path)
            else:
                if not os.path.isfile(child_path):
                    missing.append(child_path)

    walk(root_node, root_path)
    return missing


# Custom syntax highlighter for the folder structure input box
class StructureHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._build_rules()

    def _build_rules(self):
        self.highlighting_rules = []

        def add(pattern, color, bold=False, italic=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            self.highlighting_rules.append((pattern, fmt))

        add(r"[│├└─]", "#AB47BC")

        # Folder: name + trailing "/", stopping BEFORE any comment marker so
        # a "/* ... */" comment after a file name can never be swallowed
        # into the match and make that file look like a folder.
        add(r"^\s*[│├└─\s]*[\w\-.]+/(?=\s|$|#|//|/\*|<!--|--|;|%)", "#66BB6A", bold=True)

        for ext, color in FILE_COLORS_DARK.items():
            add(rf"^\s*[│├└─\s]*[\w\-]+\{ext}\b", color)

        add(r"^\s*[│├└─\s]*\.[\w\-]+\b", DOTFILE_COLOR_DARK)

        add(r"^\s*[│├└─\s]*[\w\-]+\.[\w]+", GENERIC_FILE_COLOR_DARK)

        # Comments - always the same muted italic green, distinct from
        # every file color above, applied last so it always wins.
        add(r"/\*.*?\*/", COMMENT_COLOR, italic=True)
        add(r"<!--.*?-->", COMMENT_COLOR, italic=True)
        add(r"//.*$", COMMENT_COLOR, italic=True)
        add(r"#.*$", COMMENT_COLOR, italic=True)
        add(r"(?<!\w)--.*$", COMMENT_COLOR, italic=True)
        add(r"(?<![\w.]);.*$", COMMENT_COLOR, italic=True)
        add(r"(?<!\w)%.*$", COMMENT_COLOR, italic=True)

        add(r"\b\d+\b", "#EF5350")

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


# Worker thread for structure creation
class StructureWorker(QThread):
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    completed = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, structure, root_path, delete_existing, extract_comments):
        super().__init__()
        self.structure = structure
        self.root_path = root_path
        self.delete_existing = delete_existing
        self.extract_comments = extract_comments
        self.canceled = False

    def run(self):
        try:
            result = {
                "folders_created": 0,
                "files_created": 0,
                "comments_found": 0,
                "report_file_created": False,
                "errors": [],
                "comment_data": {},
                "verified": True,
                "missing": [],
            }

            if self.delete_existing and os.path.exists(self.root_path):
                shutil.rmtree(self.root_path)
                self.message.emit("Deleted existing directory")

            root_existed = os.path.exists(self.root_path)
            os.makedirs(self.root_path, exist_ok=True)
            if not root_existed:
                result["folders_created"] += 1

            root_node, _ = parse_structure(self.structure)
            total_nodes = max(count_nodes(root_node), 1)
            processed = 0

            def create(node, current_path):
                nonlocal processed
                for child in node.children:
                    if self.canceled:
                        return
                    child_path = os.path.join(current_path, child.name)

                    if child.is_folder:
                        if not os.path.exists(child_path):
                            os.makedirs(child_path, exist_ok=True)
                            result["folders_created"] += 1
                        create(child, child_path)
                    else:
                        os.makedirs(os.path.dirname(child_path), exist_ok=True)
                        with open(child_path, "w", encoding="utf-8") as f:
                            if self.extract_comments and child.comment:
                                result["comment_data"].setdefault(child_path, []).append(
                                    f"Line {child.line_no}: {child.comment}"
                                )
                                result["comments_found"] += 1
                                f.write(child.comment + "\n")
                        result["files_created"] += 1

                    processed += 1
                    if processed % 3 == 0 or processed == total_nodes:
                        self.progress.emit(int(processed / total_nodes * 100))

            create(root_node, self.root_path)

            if self.canceled:
                self.message.emit("Operation canceled")
                return

            if result["comments_found"] > 0 and self.extract_comments:
                comments_path = os.path.join(self.root_path, "comments.txt")
                with open(comments_path, "w", encoding="utf-8") as f:
                    f.write("FolderSmith Pro - Comment Report\n")
                    f.write(
                        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write("=" * 50 + "\n\n")

                    for file_path, comments in result["comment_data"].items():
                        rel_path = os.path.relpath(file_path, self.root_path)
                        f.write(f"[File: {rel_path}]\n")
                        for comment in comments:
                            f.write(comment + "\n")
                        f.write("\n")

                result["files_created"] += 1
                result["report_file_created"] = True

            # Cross-check what we intended to create against what is
            # actually on disk.
            missing = verify_on_disk(self.root_path, root_node)
            result["missing"] = missing
            result["verified"] = len(missing) == 0

            self.completed.emit(result)

        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

    def cancel(self):
        self.canceled = True


# Worker thread for ZIP export
class ZipWorker(QThread):
    progress = pyqtSignal(int)
    completed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, source_dir, zip_path):
        super().__init__()
        self.source_dir = source_dir
        self.zip_path = zip_path
        self.canceled = False

    def run(self):
        try:
            all_files = []
            for root, _, files in os.walk(self.source_dir):
                for file in files:
                    all_files.append(os.path.join(root, file))

            total_files = len(all_files)
            if total_files == 0:
                self.error.emit("No files found to export")
                return

            with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for i, file_path in enumerate(all_files):
                    if self.canceled:
                        return

                    arcname = os.path.relpath(file_path, self.source_dir)
                    zipf.write(file_path, arcname)

                    progress = int((i + 1) / total_files * 100)
                    self.progress.emit(progress)

            self.completed.emit(self.zip_path)

        except Exception as e:
            self.error.emit(f"Export Error: {str(e)}")

    def cancel(self):
        self.canceled = True


# Modern QMessageBox with animations
class ModernMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QMessageBox {
                background-color: #2D2D30;
                color: #F1F1F1;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #F1F1F1;
                font-size: 14px;
            }
            QPushButton {
                background-color: #3D3D40;
                color: #F1F1F1;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0078D7;
                border-color: #005A9E;
            }
        """
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()


# "Deep Dive" dialog - every folder and file in the pasted structure,
# flattened into one searchable table with a colored tag for what it is.
class DeepDiveDialog(QDialog):
    def __init__(self, root_node, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deep Dive - Full Structure Breakdown")
        self.resize(780, 560)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        header = QLabel("🧭 Every folder and file, tagged so you can verify it before creating")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.setWordWrap(True)
        layout.addWidget(header)

        rows = []

        def walk(node, path, depth):
            for child in node.children:
                rel = os.path.join(path, child.name) if path else child.name
                if child.is_folder:
                    tag = "ROOT FOLDER" if depth == 0 else "SUBFOLDER"
                else:
                    tag = "FILE"
                rows.append((tag, child.name, rel, child.comment or "", depth))
                if child.is_folder:
                    walk(child, rel, depth + 1)

        walk(root_node, "", 0)

        table = QTableWidget(len(rows), 4)
        table.setHorizontalHeaderLabels(["Type", "Name", "Path", "Comment"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setWordWrap(True)

        tag_colors = {
            "ROOT FOLDER": "#2E7D32",
            "SUBFOLDER": "#1565C0",
            "FILE": "#546E7A",
        }

        for r, (tag, name, path, comment, depth) in enumerate(rows):
            pill = QLabel(tag)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                f"background-color: {tag_colors[tag]}; color: white; "
                "border-radius: 8px; padding: 3px 8px; font-weight: bold; font-size: 11px;"
            )
            cell_wrap = QWidget()
            cell_layout = QHBoxLayout(cell_wrap)
            cell_layout.setContentsMargins(6, 2, 6, 2)
            cell_layout.addWidget(pill)
            cell_layout.addStretch()
            table.setCellWidget(r, 0, cell_wrap)

            name_item = QTableWidgetItem(("    " * depth) + name)
            if tag == "FILE":
                name_item.setForeground(QColor(get_file_color(name)))
            else:
                name_item.setForeground(QColor(get_folder_color(depth)))
            table.setItem(r, 1, name_item)

            table.setItem(r, 2, QTableWidgetItem(path))

            comment_item = QTableWidgetItem(comment)
            comment_font = comment_item.font()
            comment_font.setItalic(True)
            comment_item.setFont(comment_font)
            comment_item.setForeground(QColor(COMMENT_COLOR))
            table.setItem(r, 3, comment_item)

        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(1, 200)
        table.setColumnWidth(3, 220)

        bg = "#252525"
        fg = "#F1F1F1"
        grid = "#3D3D40"
        header_bg = "#3D3D40"
        table.setStyleSheet(
            f"QTableWidget {{ background-color: {bg}; color: {fg}; gridline-color: {grid}; "
            f"border: 1px solid {grid}; }}"
            f"QTableWidget::item:selected {{ background-color: #0078D7; color: white; }}"
            f"QHeaderView::section {{ background-color: {header_bg}; color: {fg}; "
            f"padding: 6px; border: none; font-weight: bold; }}"
        )
        layout.addWidget(table)

        folder_count = sum(1 for r in rows if r[0] != "FILE")
        file_count = sum(1 for r in rows if r[0] == "FILE")
        summary = QLabel(f"Total: {folder_count} folders · {file_count} files")
        summary.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(summary)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #0078D7; color: white; padding: 8px 20px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0063B1; }"
        )
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# Main application window
class FolderSmithPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FolderSmith Pro")
        self.setMinimumSize(1000, 700)

        self.tree_diagram_detected = False

        self.structure_worker = None
        self.zip_worker = None

        self.init_ui()
        self.apply_theme()

        self.load_sample_structure()
        self.animate_entrance()

    def animate_entrance(self):
        self.showMaximized()
        self.setWindowOpacity(0)
        self.showNormal()
        self.raise_()
        self.activateWindow()

        screen = QGuiApplication.primaryScreen().availableGeometry()
        start_pos = QPoint(0, -100)
        end_pos = QPoint(0, 0)

        self.move(start_pos)

        self.entrance_animation = QParallelAnimationGroup(self)

        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(700)
        fade.setStartValue(0)
        fade.setEndValue(1)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(700)
        slide.setStartValue(start_pos)
        slide.setEndValue(end_pos)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.entrance_animation.addAnimation(fade)
        self.entrance_animation.addAnimation(slide)

        def finalize_animation():
            self.setWindowOpacity(1)
            self.showMaximized()

        self.entrance_animation.finished.connect(finalize_animation)
        self.entrance_animation.start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        self.create_menu()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Input
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        input_label = QLabel("Enter your project structure:")
        input_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(input_label)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "📁 Enter your project structure (folders must end with '/')\n"
            "\n"
            " Guidelines:\n"
            "- Use spaces or tree diagrams to represent indentation.\n"
            "- Do NOT add comments beside folder names (only files).\n"
            "- Files can have inline comments: # // /* */ <!-- --> -- ; %\n"
            "\n"
            "⚠️ Pasting tip: some apps collapse multiple spaces into one when\n"
            "you copy/paste, which can scramble indentation in tree diagrams.\n"
            "If nesting looks wrong, check the preview before creating, or use\n"
            "plain indentation (2-4 spaces per level) instead of tree symbols.\n"
            "\n"
            " Example (Plain Format):\n"
            "project/\n"
            "  main.py  # Entry point of the app\n"
            "  utils/\n"
            "    helpers.py\n"
            "  README.md  # Project documentation\n"
            "\n"
            " Example (Tree Diagram):\n"
            "project/\n"
            "├── main.py  # Entry point of the app\n"
            "├── utils/\n"
            "│   └── helpers.py\n"
            "└── README.md\n"
        )

        self.input_text.setAcceptRichText(False)
        self.input_text.setFont(QFont("Consolas", 11))
        self.highlighter = StructureHighlighter(self.input_text.document())
        left_layout.addWidget(self.input_text, 1)

        # Controls panel
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.create_btn = QPushButton("Create Structure")
        self.create_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #4CAF50; "
            "color: white; "
            "font-weight: bold; "
            "padding: 8px; "
            "border-radius: 4px; "
            "min-width: 120px;"
            "}"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #888888; }"
        )
        self.create_btn.clicked.connect(self.create_structure)
        self.create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.create_btn)

        self.simulate_btn = QPushButton("Simulate")
        self.simulate_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #2196F3; "
            "color: white; "
            "padding: 8px; "
            "border-radius: 4px; "
            "min-width: 100px;"
            "}"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        self.simulate_btn.clicked.connect(self.simulate_structure)
        self.simulate_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.simulate_btn)

        self.deepdive_btn = QPushButton("Deep Dive")
        self.deepdive_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #7E57C2; "
            "color: white; "
            "padding: 8px; "
            "border-radius: 4px; "
            "min-width: 100px;"
            "}"
            "QPushButton:hover { background-color: #6a48ac; }"
        )
        self.deepdive_btn.clicked.connect(self.open_deep_dive)
        self.deepdive_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.deepdive_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #f44336; "
            "color: white; "
            "padding: 8px; "
            "border-radius: 4px; "
            "min-width: 80px;"
            "}"
            "QPushButton:hover { background-color: #d32f2f; }"
        )
        self.clear_btn.clicked.connect(self.clear_input)
        self.clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.clear_btn)

        self.comments_cb = QCheckBox("Extract comments to comments.txt")
        self.comments_cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.comments_cb.setChecked(True)
        controls_layout.addWidget(self.comments_cb)

        self.delete_cb = QCheckBox("Delete existing folder")
        self.delete_cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        controls_layout.addWidget(self.delete_cb)

        left_layout.addLayout(controls_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #3D3D40;
            }
            QProgressBar::chunk {
                background-color: #0078D7;
                border-radius: 4px;
            }
        """
        )
        left_layout.addWidget(self.progress_bar)

        splitter.addWidget(left_panel)

        # Right panel - Preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_label = QLabel("Structure Preview:")
        preview_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(preview_label)

        # Two columns: item name (with icon + type color) and its comment
        # (always the same distinct green) - so a comment can never visually
        # blend into a file name, and long comments get their own space
        # instead of being clipped inline.
        self.tree_widget = QTreeWidget()
        self.tree_widget.setColumnCount(2)
        self.tree_widget.setHeaderLabels(["Structure", "Comment"])
        self.tree_widget.setWordWrap(True)
        self.tree_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        right_layout.addWidget(self.tree_widget, 1)

        preview_controls = QHBoxLayout()

        folder_label = QLabel("Root Folder:")
        preview_controls.addWidget(folder_label)

        self.folder_combo = QComboBox()
        self.folder_combo.addItems(
            [
                os.path.join(os.path.expanduser("~"), "FolderSmith"),
                os.path.join(os.path.expanduser("~"), "Documents", "FolderSmith"),
                os.path.join(os.path.expanduser("~"), "Desktop", "FolderSmith"),
            ]
        )
        self.folder_combo.setEditable(True)
        self.folder_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        preview_controls.addWidget(self.folder_combo, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setIcon(make_emoji_icon("📂"))
        browse_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #3D3D40; "
            "color: #F1F1F1; "
            "padding: 5px; "
            "border: 1px solid #555; "
            "border-radius: 4px;"
            "}"
            "QPushButton:hover { background-color: #0078D7; }"
        )
        browse_btn.clicked.connect(self.browse_folder)
        browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        preview_controls.addWidget(browse_btn)

        right_layout.addLayout(preview_controls)

        splitter.addWidget(right_panel)
        splitter.setSizes([600, 400])
        splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: #555;
                width: 5px;
            }
        """
        )

        self.input_text.textChanged.connect(self.update_preview)

        self.status_bar.showMessage(
            "Ready. Enter your project structure and click 'Create Structure'"
        )

        self.update_preview()

    def create_menu(self):
        menu_bar = self.menuBar()
        menu_bar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.clear_input)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Structure...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_structure)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Structure...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_structure)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        export_action = QAction("&Export as ZIP...", self)
        export_action.triggered.connect(self.export_as_zip)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("&Edit")

        clear_action = QAction("&Clear", self)
        clear_action.setShortcut("Ctrl+Shift+C")
        clear_action.triggered.connect(self.clear_input)
        edit_menu.addAction(clear_action)

        sample_action = QAction("&Load Sample", self)
        sample_action.triggered.connect(self.load_sample_structure)
        edit_menu.addAction(sample_action)

        tools_menu = menu_bar.addMenu("&Tools")

        deepdive_action = QAction("&Deep Dive...", self)
        deepdive_action.triggered.connect(self.open_deep_dive)
        tools_menu.addAction(deepdive_action)

        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        soft_action = QAction("&Create Project Structure", self)
        soft_action.triggered.connect(self.show_help)
        help_menu.addAction(soft_action)

    def apply_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(37, 37, 38))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(241, 241, 241))
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(241, 241, 241))
        palette.setColor(QPalette.ColorRole.Text, QColor(241, 241, 241))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(241, 241, 241))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(244, 67, 54))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

        input_bg, input_fg, border = "#1E1E1E", "#F1F1F1", "#555555"
        tree_bg, tree_fg = "#252525", "#F1F1F1"
        header_bg = "#3D3D40"

        self.setPalette(palette)

        self.input_text.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {input_bg};
                color: {input_fg};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 5px;
            }}
        """
        )

        self.tree_widget.setStyleSheet(
            f"""
            QTreeWidget {{
                background-color: {tree_bg};
                color: {tree_fg};
                border: 1px solid {border};
                border-radius: 5px;
            }}
            QTreeWidget::item {{ padding: 4px; }}
            QTreeWidget::item:selected {{ background-color: #0078D7; color: white; }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {tree_fg};
                padding: 5px;
                border: none;
                font-weight: bold;
            }}
        """
        )

        self.folder_combo.setStyleSheet(
            f"""
            QComboBox {{
                background-color: {input_bg}; color: {input_fg};
                border: 1px solid {border}; border-radius: 4px; padding: 5px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg}; color: {input_fg};
                selection-background-color: #0078D7;
            }}
        """
        )

        self.menuBar().setStyleSheet(
            f"""
            QMenuBar {{ background-color: {header_bg}; color: {tree_fg}; padding: 5px; }}
            QMenuBar::item {{ background-color: transparent; padding: 5px 10px; }}
            QMenuBar::item:selected {{ background-color: #0078D7; color: white; }}
            QMenu {{ background-color: {tree_bg}; color: {tree_fg}; border: 1px solid {border}; }}
            QMenu::item {{ padding: 5px 30px 5px 20px; }}
            QMenu::item:selected {{ background-color: #0078D7; color: white; }}
            QMenu::separator {{ height: 1px; background-color: {border}; }}
        """
        )

        # Re-render the preview so file/folder/comment colors stay in sync.
        self.update_preview()

    def update_preview(self):
        structure = self.input_text.toPlainText().strip()
        self.tree_widget.clear()

        if not structure:
            self.tree_diagram_detected = False
            return

        if any(char in structure for char in ["├", "│", "└"]):
            self.tree_diagram_detected = True
        else:
            self.tree_diagram_detected = False

        root_node, indent_unit = parse_structure(structure)

        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, "Project Structure")
        root_item.setIcon(0, make_emoji_icon("📁"))

        def add_children(parent_node, parent_item):
            for child in parent_node.children:
                item = QTreeWidgetItem(parent_item)
                item.setText(0, child.name)
                if child.is_folder:
                    item.setIcon(0, make_emoji_icon("📂"))
                    item.setForeground(0, QColor(get_folder_color(child.depth)))
                else:
                    item.setIcon(0, make_emoji_icon("📄"))
                    item.setForeground(0, QColor(get_file_color(child.name)))

                if child.comment:
                    item.setText(1, child.comment)
                    item.setForeground(1, QColor(COMMENT_COLOR))
                    comment_font = item.font(1)
                    comment_font.setItalic(True)
                    item.setFont(1, comment_font)

                if child.is_folder:
                    add_children(child, item)

        add_children(root_node, root_item)
        self.tree_widget.expandAll()
        self.tree_widget.resizeColumnToContents(0)
        if self.tree_widget.columnWidth(1) < 160:
            self.tree_widget.setColumnWidth(1, 220)

        if self.tree_diagram_detected:
            self.status_bar.showMessage(
                "Tree diagram detected - structure will be automatically cleaned"
            )
        elif root_node.children and len(root_node.children) > 1 and all(
            c.depth == 0 for c in root_node.children
        ):
            self.status_bar.showMessage(
                "No indentation detected - every item will be created at the same "
                "level. Indent a line with spaces to nest it inside the folder above it."
            )
        else:
            self.status_bar.showMessage(
                "Ready. Enter your project structure and click 'Create Structure'"
            )

    def open_deep_dive(self):
        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Nothing to show", "Enter a structure first.")
            return
        root_node, _ = parse_structure(text)
        if not root_node.children:
            QMessageBox.information(
                self, "Nothing to show", "No valid folders or files were found in the input."
            )
            return
        dlg = DeepDiveDialog(root_node, self)
        dlg.exec()

    def create_structure(self):
        structure = self.input_text.toPlainText().strip()
        root_path = self.folder_combo.currentText().strip()

        if not structure:
            QMessageBox.warning(
                self, "Input Error", "Please enter a project structure first."
            )
            return

        if not root_path:
            QMessageBox.warning(self, "Path Error", "Please select a root folder.")
            return

        self.create_btn.setEnabled(False)
        self.simulate_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Creating structure...")

        self.structure_worker = StructureWorker(
            structure,
            root_path,
            self.delete_cb.isChecked(),
            self.comments_cb.isChecked(),
        )

        self.structure_worker.progress.connect(self.progress_bar.setValue)
        self.structure_worker.message.connect(self.status_bar.showMessage)
        self.structure_worker.completed.connect(self.on_structure_completed)
        self.structure_worker.error.connect(self.on_structure_error)

        self.structure_worker.start()

    def simulate_structure(self):
        root_path = self.folder_combo.currentText().strip()
        if not root_path:
            QMessageBox.warning(self, "Path Error", "Please select a root folder.")
            return

        text = self.input_text.toPlainText()
        root_node, _ = parse_structure(text)
        folders, files, comments = compute_stats(root_node)
        extract = self.comments_cb.isChecked()

        msg = ModernMessageBox(self)
        msg.setWindowTitle("Structure Simulation")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            f"<b>FolderSmith Pro Simulation Results</b><br><br>"
            f"Project structure would be created at:<br>"
            f"<code>{root_path}</code><br><br>"
            f"<b>Summary:</b>"
        )
        info = (
            f"• Folders: <b>{folders}</b><br>"
            f"• Files: <b>{files}</b><br>"
            f"• Comments found: <b>{comments if extract else 0}</b>"
        )
        if not extract:
            info += "<br><i>(comment extraction is turned off)</i>"
        msg.setInformativeText(info)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def clear_input(self):
        self.input_text.clear()
        self.status_bar.showMessage("Input cleared. Ready for new structure.")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Root Folder",
            self.folder_combo.currentText(),
            QFileDialog.Option.ShowDirsOnly,
        )

        if folder:
            self.folder_combo.setCurrentText(folder)

    def on_structure_completed(self, result):
        self.create_btn.setEnabled(True)
        self.simulate_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        beep(1000, 200)

        msg = ModernMessageBox(self)
        msg.setWindowTitle("Structure Created")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            "<b>Project structure created successfully!</b><br><br><b>Summary:</b>"
        )

        files_line = f"• Files created: <b>{result['files_created']}</b>"
        if result.get("report_file_created"):
            files_line += " <i>(includes comments.txt report)</i>"

        lines = [
            f"• Folders created: <b>{result['folders_created']}</b>",
            files_line,
            f"• Comments extracted: <b>{result['comments_found']}</b>",
        ]
        if result.get("verified"):
            lines.append(
                "• Verification: <b style='color:#4CAF50;'>&#10003; Matches what's on disk</b>"
            )
        else:
            lines.append(
                f"• Verification: <b style='color:#f44336;'>&#9888; "
                f"{len(result['missing'])} item(s) could not be verified</b>"
            )
        msg.setInformativeText("<br>".join(lines))

        details = list(result["errors"])
        if result.get("missing"):
            details.append("Could not verify these on disk:")
            details.extend(result["missing"])
        if details:
            msg.setDetailedText("\n".join(details))

        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        self.status_bar.showMessage(
            f"Structure created with {result['folders_created']} folders and {result['files_created']} files."
        )

        self.structure_worker = None

    def on_structure_error(self, error_msg):
        self.create_btn.setEnabled(True)
        self.simulate_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        beep(500, 500)

        msg = ModernMessageBox(self)
        msg.setWindowTitle("Error")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(f"<b>Error creating structure:</b><br>{error_msg}")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        self.status_bar.showMessage(f"Error: {error_msg}")

        self.structure_worker = None

    def load_sample_structure(self):
        sample = """# FolderSmith Pro Sample Structure
project_root/
├── app/
│   ├── __init__.py
│   ├── main.py  # Main application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   └── logic.py  // Core functionality
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py  /* Utility functions */
│       └── validators.py
├── tests/
│   ├── unit/
│   │   └── test_core.py
│   └── integration/
│       └── test_app.py
├── docs/
│   ├── index.html  <!-- Documentation home -->
│   └── style.css
├── data/
│   ├── input/
│   └── output/
├── config/
│   └── settings.json  // Configuration settings
├── requirements.txt  # Dependencies
├── README.md  /* Project documentation */
└── .gitignore
"""
        self.input_text.setPlainText(sample)
        self.status_bar.showMessage("Sample structure loaded. Edit as needed.")

    def open_structure(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Structure File", "", "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.input_text.setPlainText(f.read())
                self.status_bar.showMessage(
                    f"Loaded structure from {os.path.basename(file_path)}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def save_structure(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Structure File",
            "project_structure.txt",
            "Text Files (*.txt);;All Files (*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.input_text.toPlainText())
                self.status_bar.showMessage(
                    f"Structure saved to {os.path.basename(file_path)}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")

    def export_as_zip(self):
        zip_path, _ = QFileDialog.getSaveFileName(
            self, "Export as ZIP", "project_structure.zip", "ZIP Archives (*.zip)"
        )

        if not zip_path:
            return

        try:
            temp_dir = os.path.join(
                os.path.expanduser("~"), "FolderSmith", "temp_export"
            )

            self.create_btn.setEnabled(False)
            self.simulate_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_bar.showMessage("Preparing ZIP export...")

            self.structure_worker = StructureWorker(
                self.input_text.toPlainText(),
                temp_dir,
                True,
                self.comments_cb.isChecked(),
            )

            self.structure_worker.progress.connect(self.progress_bar.setValue)
            self.structure_worker.message.connect(
                lambda msg: self.status_bar.showMessage(f"Export: {msg}")
            )
            self.structure_worker.completed.connect(
                lambda result: self.on_structure_ready_for_zip(
                    result, temp_dir, zip_path
                )
            )
            self.structure_worker.error.connect(self.on_export_structure_error)

            self.structure_worker.start()

        except Exception as e:
            QMessageBox.critical(
                self, "Export Error", f"Failed to start export process:\n{str(e)}"
            )
            self.reset_ui_after_export()

    def on_structure_ready_for_zip(self, result, temp_dir, zip_path):
        if "errors" in result and result["errors"]:
            QMessageBox.critical(
                self,
                "Export Error",
                "Failed to create structure for export:\n"
                + "\n".join(result["errors"]),
            )
            self.reset_ui_after_export()
            return

        self.zip_worker = ZipWorker(temp_dir, zip_path)

        self.zip_worker.progress.connect(self.progress_bar.setValue)
        self.zip_worker.completed.connect(
            lambda path: self.on_zip_completed(path, temp_dir)
        )
        self.zip_worker.error.connect(self.on_zip_error)

        self.status_bar.showMessage("Creating ZIP archive...")

        self.zip_worker.start()

    def on_export_structure_error(self, error_msg):
        QMessageBox.critical(self, "Export Error", error_msg)
        self.reset_ui_after_export()

    def on_zip_completed(self, zip_path, temp_dir):
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        msg = ModernMessageBox(self)
        msg.setWindowTitle("Export Successful")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            f"<b>Project structure exported successfully!</b><br><br>ZIP file saved to:<br><code>{zip_path}</code>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        self.status_bar.showMessage(
            f"Exported structure to {os.path.basename(zip_path)}"
        )

        self.reset_ui_after_export()

    def on_zip_error(self, error_msg):
        msg = ModernMessageBox(self)
        msg.setWindowTitle("Export Error")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(f"<b>Error during export:</b><br>{error_msg}")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        self.status_bar.showMessage(error_msg)

        self.reset_ui_after_export()

    def reset_ui_after_export(self):
        self.create_btn.setEnabled(True)
        self.simulate_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        self.structure_worker = None
        self.zip_worker = None

    def show_about(self):
        about_text = """
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    color: #f0f0f0;
                    background-color: #1e1e1e;
                    padding: 20px;
                }
                h1, h2 { margin-bottom: 5px; }
                p { margin: 5px 0; }
                ul { text-align: left; margin: 20px auto; width: fit-content; }
                li { margin-bottom: 8px; }
                .section {
                    margin-top: 40px;
                    padding-top: 10px;
                    border-top: 1px solid #444;
                }
                a { color: #4FC3F7; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .footer { margin-top: 20px; font-size: 14px; color: #ccc; }
            </style>
        </head>
        <body>
            <center>
                <h1>📁 FolderSmith Pro</h1>
                <p><strong>Version 3.0</strong></p>
                <p>Create project folder and file structures.</p>

                <p><strong> Features:</strong></p>
                <ul>
                    <li>variety of comment extraction (#, //, /* */, &lt;!-- --&gt;, --, ;, %)</li>
                    <li> Deep Dive breakdown of every folder and file</li>
                    <li> Verification of disk after creation</li>
                    <li> Export to ZIP</li>
                </ul>

                <div class="section">
                    <h2> Support & Contact</h2>
                    <p>Email: <a href="mailto:studiocoding09@gmail.com">studiocoding09@gmail.com</a></p>
                    <p>Support: <a href="https://chibuikeonuigbo.github.io/Support_Page/" target="_blank"></a></p>
                </div>

                <div class="footer">
                    <p>© 2025 FolderSmith Pro. All rights reserved.</p>
                </div>
            </center>
        </body>
        </html>
        """

        msg = ModernMessageBox(self)
        msg.setWindowTitle("About FolderSmith Pro")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def show_help(self):
        help_text = """
        <html>
        <center>
        <h1>Creating Project Structures</h1>
        <p>FolderSmith Pro makes it easy to create complex project structures.</p>

        <h2>Basic Syntax</h2>
        <table border="1" cellpadding="5" style="border-collapse: collapse; margin: 20px auto;">
            <tr><th>Element</th><th>Syntax</th><th>Example</th></tr>
            <tr><td>Folder</td><td>End with /</td><td><code>src/</code></td></tr>
            <tr><td>File</td><td>No trailing slash</td><td><code>main.py</code></td></tr>
            <tr><td>Nested Items</td><td>Indent with spaces</td><td><code>&nbsp;&nbsp;utils/</code></td></tr>
            <tr><td>Comments</td><td># // /* */ &lt;!-- --&gt; -- ; %</td><td><code># This is a comment</code></td></tr>
        </table>

        <h2>Tree Diagram Support</h2>
        <p>You can paste tree diagrams directly:</p>
        <pre style="text-align:left;margin-left: 150px;">
project/
├── app/
│   ├── main.py
│   └── utils/
└── README.md
        </pre>
        <p>The symbols (├, │, └) will be automatically processed.</p>

        <h2>⚠️ If nesting looks wrong</h2>
        <p style="max-width:480px;margin:0 auto;">
        Some chat apps, browsers, and document viewers collapse multiple spaces
        into one when you copy text. That can scramble a tree diagram's
        indentation before it ever reaches FolderSmith. Always check the live
        preview (or hit Deep Dive) before creating - if something nested wrong,
        try pasting from a plain-text source, or switch to simple space-indented
        format instead of tree symbols.
        </p>

        <h2>Color Coding</h2>
        <p>Elements are color-coded for easy identification. Comments are always
        shown in italic green, distinct from every file and folder color.</p>
        </center>
        </html>
        """

        msg = ModernMessageBox(self)
        msg.setWindowTitle("Project Structure Help")
        msg.setText(help_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def closeEvent(self, event):
        if self.structure_worker and self.structure_worker.isRunning():
            self.structure_worker.cancel()
            self.structure_worker.wait(1000)

        if self.zip_worker and self.zip_worker.isRunning():
            self.zip_worker.cancel()
            self.zip_worker.wait(1000)

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = FolderSmithPro()

    screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
    x = (screen_geometry.width() - window.width()) // 2
    y = (screen_geometry.height() - window.height()) // 2
    window.move(x, y)

    beep(800, 200)
    beep(1000, 200)

    window.showMaximized()
    sys.exit(app.exec())