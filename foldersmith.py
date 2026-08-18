# created by Chibuike, missing  some responsive features. There might still be bugs. I will improve regularly
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
    QPoint,QEvent, QTimer
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
    QPainter,QGuiApplication,
    QKeySequence,
    QShortcut,
    QTextCursor,
    QPen,
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
    QAbstractItemView,
    QInputDialog,
    QToolButton,
)


class PopupComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._swallow_release = False
        self._popup = None

    def showPopup(self):
        super().showPopup()
        self._popup = self.view().window()
        if self._popup is not None:
            # Install event filter to catch the first release
            self._popup.installEventFilter(self)
            self._swallow_release = True
            # Schedule the move to happen after the popup is shown
            QTimer.singleShot(0, self._move_popup)

    def _move_popup(self):
        if self._popup is None:
            return
        target = self.mapToGlobal(QPoint(0, self.height()))
        screen = self.screen() if hasattr(self, "screen") else QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            if target.y() + self._popup.height() > avail.bottom():
                target.setY(self.mapToGlobal(QPoint(0, 0)).y() - self._popup.height())
            target.setX(min(max(target.x(), avail.left()), avail.right() - self._popup.width()))
        self._popup.move(target)
        self._popup.resize(max(self.width(), self._popup.width()), self._popup.height())
        # After a short grace period, stop swallowing releases
        QTimer.singleShot(200, self._clear_swallow)

    def _clear_swallow(self):
        self._swallow_release = False

    def eventFilter(self, obj, event):
        if obj is self._popup and event.type() == QEvent.Type.MouseButtonRelease:
            if self._swallow_release:
                # Swallow this release so it doesn't close the popup
                return True
        return super().eventFilter(obj, event)


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


_ICON_CACHE = {}


def get_cached_icon(emoji, size=28):
    """Same as make_emoji_icon, but built once and reused. Building a
    QPixmap+QPainter per tree row was a big chunk of the lag on large
    previews, since the same handful of emoji (folder/file icons) get
    drawn thousands of times over."""
    key = (emoji, size)
    icon = _ICON_CACHE.get(key)
    if icon is None:
        icon = make_emoji_icon(emoji, size)
        _ICON_CACHE[key] = icon
    return icon


_ACTION_ICON_CACHE = {}


def get_icon_for_action(name, fallback_emoji):
    """Load an icon from the assets/ folder (undo.svg, redo.svg, ...) next
    to this script - falling back to a rendered emoji glyph if the file
    isn't there, i might have to  improve tis  later"""
    if name in _ACTION_ICON_CACHE:
        return _ACTION_ICON_CACHE[name]
    path = get_asset_path(f"{name}.svg")
    icon = QIcon(path) if os.path.isfile(path) else None
    if icon is None or icon.isNull():
        icon = make_emoji_icon(fallback_emoji, size=28)
    _ACTION_ICON_CACHE[name] = icon
    return icon


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


def parse_structure(text, ignore_connectors=False, smart_mixed=False):
    """Parse pasted folder-structure text (plain-indented, ASCII tree
    diagram, or a mix of both) into a tree of Node objects, rooted at a
    synthetic empty root.

    Depth is computed primarily from tree-diagram connector characters
    (│ ├ └), since those survive most copy/paste pipelines better than
    literal spaces do; plain-indented input falls back to leading spaces,
    using the smallest observed indent as one level.

    Two things make this "mix-tolerant":

    - A "bare" connector - a "├──"/"└──" with no "│" pipes leading it - is
      common when a diagram gets partially flattened (e.g. someone typed
      "└── processed/" straight under "raw/" with no indentation at all).
      Its literal symbol count is misleading there, so instead of trusting
      it as an absolute depth, it's resolved *relative to whatever folder
      is currently open* - "└──" attaches as a sibling of the innermost
      open item (closing that item's spot), "├──" nests one level inside
      it. A connector with real "│" pipes in front of it IS trusted
      literally, since that's a reliable, deliberate signal.
    - Fully bare lines (no connector, no leading spaces at all) carry no
      nesting signal whatsoever - guessing "deeper" or "sibling" for those
      is a coin flip that's provably wrong as often as it's right (e.g. a
      flat list where item B should nest under item A, but item C right
      after should NOT nest under B). So those are left at whatever the
      leading-space math says (top-level, if there's truly no indent) -
      an honest "I don't have enough information" rather than a
      confident-looking guess. Add indentation or a connector to any line
      that needs to nest and it will always be resolved correctly.

    The bare-connector heuristic above only activates when `smart_mixed`
    is True (the text was auto-detected, or manually marked, as Mixed).
    A properly formed tree diagram legitimately has bare "├── "/"└── "
    connectors on every depth-1 item (nothing needs a pipe in front of it
    until depth 2), so blindly re-interpreting every bare connector would
    break perfectly good tree diagrams - it's only useful once other
    lines in the same text prove the pipes aren't being used consistently.

    If `ignore_connectors` is True (used when the user has manually
    enforced "Plain indented" style), │├└─ characters are stripped and
    treated as ordinary noise instead of structural signals, so pasted
    tree-diagram glyphs can never be misread as nesting information.
    """
    lines = text.split("\n")

    if ignore_connectors:
        lines = [re.sub(r"[│├└─]", " ", l) for l in lines]

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
        has_pipe = "│" in prefix
        connector = None
        for ch in prefix:
            if ch in "├└":
                connector = ch

        top = stack[-1]

        if smart_mixed and sym_count > 0 and connector and not has_pipe:
            # Bare connector, no pipe context: resolve relative to the
            # currently open folder rather than trusting the raw count.
            base = top.depth if top is not root else 0
            depth = base if connector == "└" else base + 1
        elif sym_count > 0:
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


def detect_structure_style(text):
    """Best-effort classification of how a chunk of typed/pasted text is
    formatted: STYLE_TREE_DIAGRAM, STYLE_PLAIN_INDENT, STYLE_MIXED, or
    None if there isn't enough text to tell (fewer than 2 content lines -
    nothing to auto-switch the dropdown over).

    The rule only looks at lines *after* the first, since a hand-written
    tree diagram's very first line is conventionally the bare root name
    with no connector glyph at all - that's not a mixed signal, it's just
    how tree diagrams are written.
    """
    content_lines = [l for l in text.split("\n") if l.strip()]
    if len(content_lines) < 2:
        return None

    box_count = indent_count = flat_count = 0
    for l in content_lines[1:]:
        if any(c in l for c in "│├└"):
            box_count += 1
        elif len(l) - len(l.lstrip(" ")) > 0:
            indent_count += 1
        else:
            flat_count += 1

    if box_count == 0:
        return STYLE_PLAIN_INDENT
    if indent_count == 0 and flat_count == 0:
        return STYLE_TREE_DIAGRAM
    return STYLE_MIXED


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


# ---------------------------------------------------------------------------
# Folder -> project structure. This is FolderSmith's other core direction:
# instead of typing a structure and creating real folders from it, point it
# at a real folder on disk and it scans that folder into the same Node tree
# the rest of the app already understands - so the preview, Deep Dive, and
# text export all work on a scanned folder exactly like they do on typed
# text. Scanning always happens on a background thread (FolderScanWorker
# below) so importing a large folder never freezes the UI.
# ---------------------------------------------------------------------------
class FolderTooLargeError(Exception):
    pass


DEFAULT_SKIP_ENTRIES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".idea",
    ".vscode", ".mypy_cache", ".pytest_cache", ".DS_Store", "dist",
    "build", ".next", ".pytest_cache",
}
MAX_IMPORT_NODES = 20000
LAZY_LOAD_THRESHOLD = 150  # nodes; above this, the preview tree populates on-demand


def build_tree_from_folder(root_path, skip_entries=None, should_cancel=None, on_progress=None):
    """Walk a real folder on disk into a Node tree. Runs entirely on a
    worker thread. `should_cancel` is polled periodically so a scan of a
    huge folder can be aborted instantly instead of blocking shutdown.
    `on_progress(count)` is called every ~200 items so the status bar can
    show live progress without flooding the Qt event queue with signals.
    """
    skip_entries = skip_entries if skip_entries is not None else DEFAULT_SKIP_ENTRIES
    root_name = os.path.basename(os.path.normpath(root_path)) or root_path
    root = Node(name=root_name, is_folder=True, depth=0)
    count = 0

    def walk(node, path, depth):
        nonlocal count
        if should_cancel and should_cancel():
            return
        try:
            entries = sorted(
                os.scandir(path),
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
            )
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            return
        for entry in entries:
            if should_cancel and should_cancel():
                return
            if entry.name in skip_entries:
                continue
            count += 1
            if count > MAX_IMPORT_NODES:
                raise FolderTooLargeError(
                    f"This folder has more than {MAX_IMPORT_NODES:,} items.\n"
                    "Pick a smaller or more specific folder to import."
                )
            if on_progress and count % 200 == 0:
                on_progress(count)
            is_dir = entry.is_dir(follow_symlinks=False)
            child = Node(name=entry.name, is_folder=is_dir, depth=depth + 1)
            child.parent = node
            node.children.append(child)
            if is_dir:
                walk(child, entry.path, depth + 1)

    walk(root, root_path, 0)
    return root, count


class FolderScanWorker(QThread):
    """Scans a folder on a background thread. Keeping this off the GUI
    thread is what fixes the old lag/"Not Responding" freeze on big
    imports - the disk walk never blocks Qt's event loop."""

    progress = pyqtSignal(int)
    completed = pyqtSignal(object)  # (wrapper_root_node, item_count)
    error = pyqtSignal(str)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self._canceled = False

    def cancel(self):
        self._canceled = True

    def _is_canceled(self):
        return self._canceled

    def run(self):
        try:
            scanned_root, count = build_tree_from_folder(
                self.folder_path,
                should_cancel=self._is_canceled,
                on_progress=self.progress.emit,
            )
        except FolderTooLargeError as e:
            self.error.emit(str(e))
            return
        except Exception as e:
            self.error.emit(f"Could not read that folder:\n{e}")
            return

        if self._canceled:
            return

        # Wrap so it has the same shape as parse_structure()'s synthetic
        # root (a root whose children are the top-level items) - this lets
        # every renderer/consumer in the app treat a scanned folder exactly
        # like typed text.
        wrapper = Node(name="", is_folder=True, depth=-1)
        scanned_root.parent = wrapper
        wrapper.children = [scanned_root]
        self.completed.emit((wrapper, count))


# ---------------------------------------------------------------------------
# Rendering a Node tree back to text, in either of the two project-tree
# styles people commonly use. Both directions (typed text -> tree, and
# folder scan -> tree) funnel through the SAME render functions, so the
# "Tree style" toggle affects a pasted structure and an imported folder
# identically.
# ---------------------------------------------------------------------------
STYLE_TREE_DIAGRAM = "tree"
STYLE_PLAIN_INDENT = "indent"
# Not a real output format - text can't be "rendered as mixed". It only
# ever appears as an auto-detected label telling the user their input
# combines both conventions; picking Tree diagram or Plain indented from
# the dropdown cleans it up into one consistent style.
STYLE_MIXED = "mixed"


def render_structure_text(root_node, style, indent_unit=2):
    # STYLE_MIXED has no output format of its own - it only ever labels
    # detected input. Rendering it falls back to the tree diagram, which
    # is also the cleanup path when the user manually picks "Mixed" to
    # normalize ambiguous text.
    if style == STYLE_PLAIN_INDENT:
        return _render_plain_indent(root_node, indent_unit)
    return _render_tree_diagram(root_node)


def _render_plain_indent(root_node, indent_unit=2):
    lines = []

    def walk(node, depth):
        for child in node.children:
            pad = " " * (depth * indent_unit)
            name = child.name + ("/" if child.is_folder else "")
            if child.comment:
                # child.comment already includes its own marker (#, //,
                # /* */, <!-- -->, ...) from strip_comment(), so it's
                # appended as-is - prefixing another "# " here would double
                # up the marker (e.g. "# // Core functionality").
                lines.append(f"{pad}{name}  {child.comment}")
            else:
                lines.append(f"{pad}{name}")
            if child.is_folder:
                walk(child, depth + 1)

    walk(root_node, 0)
    return "\n".join(lines)


def _render_tree_diagram(root_node):
    """Render as an ASCII tree diagram. Top-level item(s) are written bare
    (no ├──/└── glyph) - the same convention a hand-written diagram or the
    `tree` command uses, where the very first line is just the root name
    and only its *nested* children get connector glyphs. Only descendants
    (depth >= 1) are prefixed."""
    lines = []

    def walk(node, prefix):
        children = node.children
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            connector = "└── " if is_last else "├── "
            name = child.name + ("/" if child.is_folder else "")
            line = prefix + connector + name
            if child.comment:
                # See _render_plain_indent: comment already carries its own
                # marker, so don't prefix another "# " here.
                line += f"  {child.comment}"
            lines.append(line)
            if child.is_folder:
                extension = "    " if is_last else "│   "
                walk(child, prefix + extension)

    for top in root_node.children:
        name = top.name + ("/" if top.is_folder else "")
        line = name
        if top.comment:
            line += f"  {top.comment}"
        lines.append(line)
        if top.is_folder:
            walk(top, "")

    return "\n".join(lines)


# The full annotated example that demonstrates every supported comment
# style (#, //, /* */, <!-- -->) and multi-level nesting. Defined once here
# so both the "Load Sample" menu action and the Preset dropdown show the
# exact same text - picking either one can never disagree with the other.
SAMPLE_STRUCTURE = """# FolderSmith Pro Sample Structure
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

# Ready-made project structures - no AI, no network, no API key. Picking
# one just fills the input with well-known layouts for common project types.
PRESET_STRUCTURES = {
    "Sample (all comment styles)": SAMPLE_STRUCTURE,
    "Python Package": (
        "my_package/\n"
        "  my_package/\n"
        "    __init__.py\n"
        "    core.py\n"
        "  tests/\n"
        "    test_core.py\n"
        "  pyproject.toml\n"
        "  README.md\n"
        "  .gitignore\n"
    ),
    "Flask Web App": (
        "flask_app/\n"
        "  app/\n"
        "    __init__.py\n"
        "    routes.py\n"
        "    models.py\n"
        "    templates/\n"
        "      index.html\n"
        "    static/\n"
        "      css/\n"
        "      js/\n"
        "  tests/\n"
        "    test_app.py\n"
        "  requirements.txt\n"
        "  .env\n"
        "  .gitignore\n"
        "  README.md\n"
    ),
    "React App": (
        "react_app/\n"
        "  public/\n"
        "    index.html\n"
        "  src/\n"
        "    components/\n"
        "    App.jsx\n"
        "    index.jsx\n"
        "  package.json\n"
        "  .gitignore\n"
        "  README.md\n"
    ),
    "Flutter App": (
        "flutter_app/\n"
        "  lib/\n"
        "    main.dart\n"
        "    screens/\n"
        "    widgets/\n"
        "  assets/\n"
        "    images/\n"
        "  test/\n"
        "  pubspec.yaml\n"
        "  README.md\n"
    ),
    "Node/Express API": (
        "express_api/\n"
        "  src/\n"
        "    routes/\n"
        "    controllers/\n"
        "    models/\n"
        "    index.js\n"
        "  tests/\n"
        "  package.json\n"
        "  .env\n"
        "  .gitignore\n"
        "  README.md\n"
    ),
    "Data Science Project": (
        "ds_project/\n"
        "  data/\n"
        "    raw/\n"
        "    processed/\n"
        "  notebooks/\n"
        "  src/\n"
        "    __init__.py\n"
        "  models/\n"
        "  requirements.txt\n"
        "  README.md\n"
    ),
    "Empty Project": (
        "new_project/\n"
        "  src/\n"
        "  docs/\n"
        "  tests/\n"
        "  README.md\n"
        "  .gitignore\n"
    ),
}


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

    def __init__(self, structure, root_path, delete_existing, extract_comments,
                 ignore_connectors=False, smart_mixed=False):
        super().__init__()
        self.structure = structure
        self.root_path = root_path
        self.delete_existing = delete_existing
        self.extract_comments = extract_comments
        self.ignore_connectors = ignore_connectors
        self.smart_mixed = smart_mixed
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

            root_node, _ = parse_structure(
                self.structure,
                ignore_connectors=self.ignore_connectors,
                smart_mixed=self.smart_mixed,
            )
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
        table.setAlternatingRowColors(False)
        table.setWordWrap(True)

        # Deliberately just two accent colors plus the existing comment
        # color (3 total) - everything else in the table stays plain text
        # in the default foreground. Folders and files are told apart by
        # color alone on the Type column; no pill/badge shapes, no
        # per-extension rainbow, no striped rows.
        FOLDER_ACCENT = "#59A5D8"
        FILE_ACCENT = "#D9A15B"

        for r, (tag, name, path, comment, depth) in enumerate(rows):
            accent = FOLDER_ACCENT if tag != "FILE" else FILE_ACCENT

            tag_item = QTableWidgetItem(tag)
            tag_font = tag_item.font()
            tag_font.setBold(True)
            tag_item.setFont(tag_font)
            tag_item.setForeground(QColor(accent))
            table.setItem(r, 0, tag_item)

            name_item = QTableWidgetItem(("    " * depth) + name)
            name_item.setForeground(QColor(accent))
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

        bg = "#1B1B1B"
        fg = "#E8E8E8"
        grid = "#333333"
        header_bg = "#242424"
        table.setStyleSheet(
            f"QTableWidget {{ background-color: {bg}; color: {fg}; gridline-color: {grid}; "
            f"border: 1px solid {grid}; }}"
            f"QTableWidget::item {{ background-color: transparent; }}"
            f"QTableWidget::item:selected {{ background-color: #3A3A3A; color: {fg}; }}"
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


# The structure text box, with one small addition: a signal that fires
# right after a paste completes (Ctrl+V, middle-click, or drag-drop text),
# so "Enforce this style" can auto-correct pasted content immediately
# instead of only on the next debounced pause in typing.
class StructureTextEdit(QTextEdit):
    """The structure text box, with VS Code-style multi-cursor editing.

    - Alt+click: add a secondary cursor at the click point.
    - Alt+click on an existing secondary cursor: remove it.
    - Alt+Shift+click: add a column of cursors, one per line, from the
      current cursor's line down (or up) to the clicked line, all at the
      clicked column (clamped to each line's length).
    - Escape: clear every secondary cursor.
    - Alt+Up / Alt+Down: move the current line up/down.
    - Alt+Shift+Up / Alt+Shift+Down: duplicate the current line up/down
      (VS Code's "Copy Line Up/Down").
    - Home: first press goes to the first non-whitespace character on the
      line, a second press (already there) goes to true column 0 - VS
      Code's "smart Home".

    Typing, Backspace, Delete, Enter and Tab are applied to *every* cursor
    at once when secondary cursors exist - not just drawn as decoration.
    Edits are applied right-to-left across cursor positions so earlier
    edits never invalidate the positions of cursors still waiting their
    turn, which is what makes doing this safely on a plain QTextEdit
    possible without a custom text-layout engine.

    Line move/duplicate act on the primary cursor only and clear any
    secondary cursors first - swapping or duplicating several
    independently-positioned lines safely at once is a lot more
    bookkeeping for a use case that's rare in practice (people move/
    duplicate one line at a time even when they're mid multi-cursor edit).
    Full VS Code-style column/word "hypotenuse" range highlighting isn't
    implemented either - this gives you a working column of caret
    positions to type into, not highlighted column *selections*.
    """

    pasted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extra_cursors = []  # list[QTextCursor], secondary carets only
        self._caret_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start(500)
        self._home_toggle_col = None

    # -- painting the secondary carets ------------------------------------

    def _toggle_blink(self):
        if not self._extra_cursors:
            return
        self._caret_visible = not self._caret_visible
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._extra_cursors or not self._caret_visible:
            return
        painter = QPainter(self.viewport())
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Text), 2))
        for cur in self._extra_cursors:
            rect = self.cursorRect(cur)
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        painter.end()

    # -- helpers ------------------------------------------------------------

    def _cursor_at(self, pos):
        c = QTextCursor(self.document())
        c.setPosition(max(0, min(pos, self.document().characterCount() - 1)))
        return c

    def _normalize_extra_cursors(self):
        """Drop any secondary cursor that's collided with the primary
        cursor or with another secondary cursor after a move/edit."""
        primary_pos = self.textCursor().position()
        seen = {primary_pos}
        deduped = []
        for c in self._extra_cursors:
            p = c.position()
            if p not in seen:
                seen.add(p)
                deduped.append(c)
        self._extra_cursors = deduped

    def clear_extra_cursors(self):
        if self._extra_cursors:
            self._extra_cursors = []
            self.viewport().update()

    def setPlainText(self, text):
        # Any wholesale text replacement (undo/redo, style reformat, a
        # tree edit, Import Folder, ...) invalidates whatever the extra
        # cursors were pointing at - always start clean.
        self._extra_cursors = []
        super().setPlainText(text)

    # -- adding cursors with the mouse --------------------------------------

    def _add_or_remove_cursor(self, point):
        pos = self.cursorForPosition(point).position()
        if pos == self.textCursor().position():
            return  # can't stack a clone directly on the real cursor
        for i, c in enumerate(self._extra_cursors):
            if c.position() == pos:
                del self._extra_cursors[i]  # click again to remove it
                self.viewport().update()
                return
        self._extra_cursors.append(self._cursor_at(pos))
        self.viewport().update()

    def _add_column_cursors(self, point):
        click_cursor = self.cursorForPosition(point)
        anchor_line = self.textCursor().blockNumber()
        click_line = click_cursor.blockNumber()
        start_line, end_line = sorted((anchor_line, click_line))
        col = click_cursor.positionInBlock()

        doc = self.document()
        positions = []
        for line in range(start_line, end_line + 1):
            block = doc.findBlockByNumber(line)
            if not block.isValid():
                continue
            line_col = min(col, len(block.text()))
            positions.append(block.position() + line_col)
        if not positions:
            return

        self.setTextCursor(self._cursor_at(positions[0]))
        self._extra_cursors = [self._cursor_at(p) for p in positions[1:]]
        self._normalize_extra_cursors()
        self.viewport().update()

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            point = event.position().toPoint()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._add_column_cursors(point)
            else:
                self._add_or_remove_cursor(point)
            event.accept()
            return
        self.clear_extra_cursors()
        super().mousePressEvent(event)

    def insertFromMimeData(self, source):
        self._extra_cursors = []
        super().insertFromMimeData(source)
        self.pasted.emit()

    # -- applying one edit to every cursor at once --------------------------

    def _apply_to_all_cursors(self, edit_fn):
        """Apply edit_fn to the primary cursor and every secondary cursor
        at once.

        The bug this replaces: it used to snapshot each cursor's
        position as a plain integer, edit a *fresh* cursor built from
        that integer, and record wherever that fresh cursor ended up -
        then reuse those recorded integers to rebuild the cursor list
        for next time. That recording goes stale the instant *another*
        cursor, positioned earlier in the document, inserts or deletes
        text afterward - everything after it shifts, but the already
        recorded integer doesn't know that. It drifted a little more
        with every single keystroke, which is exactly why five lines of
        "happy" came out fine on the first letter and garbage everywhere
        after.

        The actual fix is to not track plain integers at all: every
        cursor here (self.textCursor() and everything in
        self._extra_cursors) is a genuine *live* QTextCursor tied to
        this document, and Qt automatically keeps every other live
        cursor correctly repositioned whenever any one of them edits the
        document - insert, delete, whatever. So editing the real cursor
        objects directly, in any order, is already correct with no
        offset math needed.
        """
        primary = self.textCursor()
        cursors = [primary] + self._extra_cursors

        primary.beginEditBlock()
        for cur in cursors:
            edit_fn(cur)
        primary.endEditBlock()

        self.setTextCursor(primary)
        self._extra_cursors = cursors[1:]
        self._normalize_extra_cursors()
        self.viewport().update()

    def _move_all_cursors(self, op):
        primary = self.textCursor()
        cursors = [primary] + self._extra_cursors
        for cur in cursors:
            cur.movePosition(op, QTextCursor.MoveMode.MoveAnchor)
        self.setTextCursor(primary)
        self._extra_cursors = cursors[1:]
        self._normalize_extra_cursors()
        self.viewport().update()

    _NAV_OPS = {
        Qt.Key.Key_Left: QTextCursor.MoveOperation.Left,
        Qt.Key.Key_Right: QTextCursor.MoveOperation.Right,
        Qt.Key.Key_Up: QTextCursor.MoveOperation.Up,
        Qt.Key.Key_Down: QTextCursor.MoveOperation.Down,
        Qt.Key.Key_Home: QTextCursor.MoveOperation.StartOfLine,
        Qt.Key.Key_End: QTextCursor.MoveOperation.EndOfLine,
    }

    def _handle_multicursor_key(self, event):
        """Returns True if this key was handled across all cursors."""
        text = event.text()
        key = event.key()
        mods = event.modifiers()

        if text and text.isprintable() and not (mods & Qt.KeyboardModifier.ControlModifier):
            self._apply_to_all_cursors(lambda c, t=text: c.insertText(t))
            return True
        if key == Qt.Key.Key_Backspace:
            self._apply_to_all_cursors(lambda c: c.deletePreviousChar())
            return True
        if key == Qt.Key.Key_Delete:
            self._apply_to_all_cursors(lambda c: c.deleteChar())
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._apply_to_all_cursors(lambda c: c.insertText("\n"))
            return True
        if key == Qt.Key.Key_Tab:
            self._apply_to_all_cursors(lambda c: c.insertText("\t"))
            return True
        if key in self._NAV_OPS:
            self._move_all_cursors(self._NAV_OPS[key])
            return True
        # Anything else (Ctrl+C, Ctrl+V, Ctrl+A, function keys, ...) isn't
        # multi-cursor-aware here - drop back to single-cursor behavior
        # rather than leave the secondary cursors in an undefined state.
        self.clear_extra_cursors()
        return False

    # -- line move / duplicate ----------------------------------------------

    def _move_line(self, direction):
        cursor = self.textCursor()
        doc = self.document()
        block = cursor.block()
        target_number = block.blockNumber() + direction
        if target_number < 0 or target_number >= doc.blockCount():
            return
        col = cursor.positionInBlock()
        this_text = block.text()
        other_block = doc.findBlockByNumber(target_number)
        other_text = other_block.text()
        top_block, bottom_block = (other_block, block) if direction < 0 else (block, other_block)

        span = QTextCursor(doc)
        span.setPosition(top_block.position())
        span.setPosition(
            bottom_block.position() + len(bottom_block.text()), QTextCursor.MoveMode.KeepAnchor
        )
        replacement = (
            f"{this_text}\n{other_text}" if direction < 0 else f"{other_text}\n{this_text}"
        )
        span.beginEditBlock()
        span.insertText(replacement)
        span.endEditBlock()

        new_block = doc.findBlockByNumber(target_number)
        new_col = min(col, len(new_block.text()))
        self.setTextCursor(self._cursor_at(new_block.position() + new_col))
        self.clear_extra_cursors()
        self.ensureCursorVisible()

    def _duplicate_line(self, direction):
        cursor = self.textCursor()
        doc = self.document()
        block = cursor.block()
        text = block.text()
        col = cursor.positionInBlock()

        insert_cursor = QTextCursor(doc)
        insert_cursor.beginEditBlock()
        if direction < 0:
            insert_cursor.setPosition(block.position())
            insert_cursor.insertText(text + "\n")
            new_pos = block.position() + col
        else:
            insert_cursor.setPosition(block.position() + len(text))
            insert_cursor.insertText("\n" + text)
            new_pos = block.position() + len(text) + 1 + col
        insert_cursor.endEditBlock()

        self.setTextCursor(self._cursor_at(new_pos))
        self.clear_extra_cursors()
        self.ensureCursorVisible()

    # -- key dispatch ---------------------------------------------------------

    def keyPressEvent(self, event):
        mods = event.modifiers()
        key = event.key()
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if alt and shift and key == Qt.Key.Key_Up:
            self._duplicate_line(-1)
            event.accept()
            return
        if alt and shift and key == Qt.Key.Key_Down:
            self._duplicate_line(1)
            event.accept()
            return
        if alt and not shift and key == Qt.Key.Key_Up:
            self._move_line(-1)
            event.accept()
            return
        if alt and not shift and key == Qt.Key.Key_Down:
            self._move_line(1)
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._extra_cursors:
            self.clear_extra_cursors()
            event.accept()
            return

        # Smart Home (single-cursor only): first press -> first
        # non-whitespace character, second press from there -> column 0.
        if key == Qt.Key.Key_Home and not shift and not self._extra_cursors:
            cursor = self.textCursor()
            block_text = cursor.block().text()
            first_non_ws = len(block_text) - len(block_text.lstrip())
            if cursor.positionInBlock() == first_non_ws:
                target = 0
            else:
                target = first_non_ws
            cursor.setPosition(cursor.block().position() + target)
            self.setTextCursor(cursor)
            event.accept()
            return

        if self._extra_cursors and self._handle_multicursor_key(event):
            event.accept()
            return

        super().keyPressEvent(event)


# The live preview tree.
#
# QTreeWidget's built-in "InternalMove" drag mode already does the visual
# work of letting an item be dragged onto a new parent - but it doesn't
# tell anyone when a drop finished, and Delete/Backspace do nothing by
# default. This subclass adds both: it emits `about_to_change` right
# before Qt performs a drop (so the caller can snapshot the "before"
# state for undo) and `changed_by_user` right after (so the caller can
# turn the new arrangement back into text), and it turns Delete/Backspace
# into the same `delete_requested` signal the right-click menu uses.
#
# Text stays authoritative: every one of these actions ends with the tree
# being re-rendered to text and then rebuilt fresh from that text, so the
# widget can never silently drift out of sync with what Create Structure
# would actually produce.
class InteractiveTreeWidget(QTreeWidget):
    about_to_change = pyqtSignal()
    changed_by_user = pyqtSignal()
    delete_requested = pyqtSignal()
    context_menu_requested = pyqtSignal(object)  # QPoint

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # PyQt6 won't let one signal connect straight to another when their
        # argument signatures don't match exactly (QPoint vs a generic
        # object), so re-emit through a small wrapper instead.
        self.customContextMenuRequested.connect(
            lambda pos: self.context_menu_requested.emit(pos)
        )

    def dropEvent(self, event):
        self.about_to_change.emit()
        super().dropEvent(event)
        self.changed_by_user.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selectedItems():
            self.delete_requested.emit()
            return
        super().keyPressEvent(event)


# Main application window
class FolderSmithPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FolderSmith Pro")
        self.setMinimumSize(1000, 700)

        self.tree_diagram_detected = False
        self.tree_style = STYLE_TREE_DIAGRAM
        self._preview_root_item = None

        # Unified undo/redo: every entry is a full snapshot of the text
        # box's content from just before a change. Covers both typed edits
        # (coalesced into one step per pause, like any normal editor) and
        # interactive preview edits (drag-move, create, rename, delete -
        # each its own discrete step). No cap on how many steps are kept.
        self._undo_stack = []
        self._redo_stack = []
        self._last_committed_text = ""
        self._pending_typing_baseline = None
        self._suspend_undo_capture = False
        self._typing_debounce = QTimer(self)
        self._typing_debounce.setSingleShot(True)
        self._typing_debounce.setInterval(700)
        self._typing_debounce.timeout.connect(self._commit_typing_undo_step)

        self.structure_worker = None
        self.zip_worker = None
        self.scan_worker = None

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

        input_label = QLabel("Project Structure")
        input_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(input_label)

        subtitle = QLabel(
            "Import a real folder to turn it into a project structure, or "
            "type/paste one below and create the real folders from it."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #9AA0A6; font-size: 12px;")
        left_layout.addWidget(subtitle)

        # Source row - this is the primary "folder -> project structure"
        # entry point, so it sits above the text box, not buried below it.
        source_row = QHBoxLayout()
        source_row.setSpacing(10)

        self.import_folder_btn = QPushButton("Import Folder…")
        self.import_folder_btn.setIcon(make_emoji_icon("📥"))
        self.import_folder_btn.setToolTip(
            "Scan a real folder on disk and turn it into a project structure"
        )
        self.import_folder_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #E08E45; "
            "color: #1E1E1E; "
            "font-weight: bold; "
            "padding: 8px 14px; "
            "border: none; "
            "border-radius: 4px; "
            "}"
            "QPushButton:hover { background-color: #EFA968; }"
            "QPushButton:disabled { background-color: #888888; }"
        )
        self.import_folder_btn.clicked.connect(self.import_folder)
        self.import_folder_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        source_row.addWidget(self.import_folder_btn)

        preset_label = QLabel("Preset:")
        source_row.addWidget(preset_label)

        self.preset_combo = PopupComboBox()
        # self.preset_combo = QComboBox()
        self.preset_combo.addItem("Choose a preset…")
        self.preset_combo.addItems(sorted(PRESET_STRUCTURES.keys()))
        self.preset_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.preset_combo.activated.connect(self.load_selected_preset)
        source_row.addWidget(self.preset_combo, 1)

        style_label = QLabel("Tree style:")
        source_row.addWidget(style_label)

        self.tree_style_combo = PopupComboBox()
        self.tree_style_combo.addItem("Tree diagram (├── └──)", STYLE_TREE_DIAGRAM)
        self.tree_style_combo.addItem("Plain indented", STYLE_PLAIN_INDENT)
        self.tree_style_combo.addItem("Mixed (auto-detected)", STYLE_MIXED)
        self.tree_style_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.tree_style_combo.currentIndexChanged.connect(self.on_tree_style_changed)
        source_row.addWidget(self.tree_style_combo)

        self.enforce_style_cb = QCheckBox("Enforce this style")
        self.enforce_style_cb.setToolTip(
            "Lock the Tree style dropdown to whatever you pick here instead of "
            "letting it auto-switch based on what you type. Turn this on if you "
            "want to type plain indentation while your text happens to still "
            "contain tree characters (├ └ │), so they're never mistaken for "
            "structure and mixed-style detection never kicks in."
        )
        self.enforce_style_cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.enforce_style_cb.stateChanged.connect(self._on_enforce_toggled)
        source_row.addWidget(self.enforce_style_cb)

        left_layout.addLayout(source_row)

        self.input_text = StructureTextEdit()
        self.input_text.setPlaceholderText(
            "📁 Enter your project structure (folders must end with '/')\n"
            "Or click 'Import Folder…' above to generate this from a real folder.\n"
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
        # Undo/redo is handled by our own unified stack (see
        # _on_input_text_changed / _do_undo / _do_redo) so typed edits and
        # interactive preview edits - drag, create, delete - share a single
        # Ctrl+Z/Ctrl+Y history instead of two that fight each other.
        self.input_text.setUndoRedoEnabled(False)
        self.input_text.setFont(QFont("Consolas", 11))
        self.highlighter = StructureHighlighter(self.input_text.document())
        self.input_text.installEventFilter(self)
        self.input_text.pasted.connect(self._on_text_pasted)
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

        preview_header = QHBoxLayout()
        preview_label = QLabel("Structure Preview:")
        preview_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        preview_header.addWidget(preview_label)
        preview_hint = QLabel("Drag to move · right-click to add/rename/convert/delete · Del key removes")
        preview_hint.setStyleSheet("color: #8A8A8A; font-size: 11px;")
        preview_header.addWidget(preview_hint)
        preview_header.addStretch()

        self.undo_btn = QToolButton()
        self.undo_btn.setIcon(get_icon_for_action("undo", "↩"))
        self.undo_btn.setIconSize(QSize(28, 28))
        self.undo_btn.setFixedSize(40, 40)
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.undo_btn.setAutoRaise(True)
        self.undo_btn.clicked.connect(self._do_undo)
        preview_header.addWidget(self.undo_btn)

        self.redo_btn = QToolButton()
        self.redo_btn.setIcon(get_icon_for_action("redo", "↪"))
        self.redo_btn.setIconSize(QSize(28, 28))
        self.redo_btn.setFixedSize(40, 40)
        self.redo_btn.setToolTip("Redo (Ctrl+Y)")
        self.redo_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.redo_btn.setAutoRaise(True)
        self.redo_btn.clicked.connect(self._do_redo)
        preview_header.addWidget(self.redo_btn)

        right_layout.addLayout(preview_header)

        # Two columns: item name (with icon + type color) and its comment
        # (always the same distinct green) - so a comment can never visually
        # blend into a file name, and long comments get their own space
        # instead of being clipped inline.
        self.tree_widget = InteractiveTreeWidget()
        self.tree_widget.setColumnCount(2)
        self.tree_widget.setHeaderLabels(["Structure", "Comment"])
        self.tree_widget.setWordWrap(True)
        self.tree_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.tree_widget.setUniformRowHeights(True)
        self.tree_widget.itemExpanded.connect(self._on_tree_item_expanded)
        self.tree_widget.about_to_change.connect(self._snapshot_before_tree_edit)
        self.tree_widget.changed_by_user.connect(self._on_tree_edited)
        self.tree_widget.delete_requested.connect(self._delete_selected_tree_items)
        self.tree_widget.context_menu_requested.connect(self._show_tree_context_menu)

        # Ctrl+Z/Ctrl+Y work here too, scoped to this widget so they can't
        # double-fire alongside the text box's own event-filter-based undo.
        self.tree_undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self.tree_widget)
        self.tree_undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.tree_undo_shortcut.activated.connect(self._do_undo)
        self.tree_redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self.tree_widget)
        self.tree_redo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.tree_redo_shortcut.activated.connect(self._do_redo)
        self.tree_redo_shortcut_alt = QShortcut(QKeySequence("Ctrl+Y"), self.tree_widget)
        self.tree_redo_shortcut_alt.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.tree_redo_shortcut_alt.activated.connect(self._do_redo)
        right_layout.addWidget(self.tree_widget, 1)

        preview_controls = QHBoxLayout()

        folder_label = QLabel("Root Folder:")
        preview_controls.addWidget(folder_label)

        self.folder_combo = PopupComboBox()
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
            "padding: 6px 12px; "
            "border: none; "
            "border-radius: 4px;"
            "}"
            "QPushButton:hover { background-color: #7C6FA6; }"
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

        self.input_text.textChanged.connect(self._on_input_text_changed)

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

        import_action = QAction("&Import Folder...", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self.import_folder)
        tools_menu.addAction(import_action)

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

        shortcuts_action = QAction("&Shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)

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
        # A softened purple accent - used for selection/highlight states
        # everywhere (tree rows, combo dropdowns, menus) instead of a
        # bright saturated purple, per feedback that the old highlight
        # was too bright.
        accent = "#7C6FA6"
        palette.setColor(QPalette.ColorRole.Highlight, QColor(accent))
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
                selection-background-color: {accent};
                selection-color: white;
            }}
        """
        )

        # Selection covers the branch (expand-arrow) column too, so a
        # selected row reads as one flat highlighted bar instead of a
        # highlight block that looks indented/bordered next to the arrow.
        self.tree_widget.setStyleSheet(
            f"""
            QTreeWidget {{
                background-color: {tree_bg};
                color: {tree_fg};
                border: 1px solid {border};
                border-radius: 5px;
                outline: 0;
            }}
            QTreeWidget::item {{ padding: 4px; border: none; }}
            QTreeWidget::item:selected {{ background-color: {accent}; color: white; }}
            QTreeWidget::branch:selected {{ background-color: {accent}; }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {tree_fg};
                padding: 5px;
                border: none;
                font-weight: bold;
            }}
        """
        )

        # Same flat treatment (background + radius, no visible border) on
        # every button/combo that shares a row, so a button sitting next
        # to a combo box never looks like a mismatched extra element.
        flat_control = f"""
            QPushButton {{
                background-color: {header_bg}; color: {input_fg};
                border: none; border-radius: 4px; padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {accent}; }}
            QPushButton:disabled {{ background-color: #2A2A2C; color: #777; }}
            QComboBox {{
                background-color: {header_bg}; color: {input_fg};
                border: none; border-radius: 4px; padding: 5px 8px;
            }}
            QComboBox:hover {{ background-color: #46464A; }}
            QComboBox::drop-down {{ border: none; width: 20px; background: transparent; }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg}; color: {input_fg};
                border: 1px solid {border};
                selection-background-color: {accent};
                selection-color: white;
                outline: 0;
            }}
        """
        for widget in (self.preset_combo, self.tree_style_combo, self.folder_combo):
            widget.setStyleSheet(flat_control)

        self.menuBar().setStyleSheet(
            f"""
            QMenuBar {{ background-color: {header_bg}; color: {tree_fg}; padding: 5px; }}
            QMenuBar::item {{ background-color: transparent; padding: 5px 10px; }}
            QMenuBar::item:selected {{ background-color: {accent}; color: white; }}
            QMenu {{ background-color: {tree_bg}; color: {tree_fg}; border: 1px solid {border}; }}
            QMenu::item {{ padding: 5px 30px 5px 20px; }}
            QMenu::item:selected {{ background-color: {accent}; color: white; }}
            QMenu::separator {{ height: 1px; background-color: {border}; }}
        """
        )

        # Re-render the preview so file/folder/comment colors stay in sync.
        self.update_preview()

    # --- Preview tree building --------------------------------------------
    # Below LAZY_LOAD_THRESHOLD nodes, the whole tree is built and expanded
    # up front - nicest for typical hand-typed structures. Above it (a big
    # imported folder), only the visible level is ever realized as real
    # QTreeWidgetItems; each folder gets a single "Loading…" placeholder
    # that's swapped for its real children only when the user expands it.
    # This is what keeps a huge import from freezing the UI: Qt never has
    # to construct/lay out thousands of widget rows it doesn't need yet.
    _LAZY_TAG = "__lazy_placeholder__"

    def _build_item_for_node(self, node):
        item = QTreeWidgetItem()
        item.setText(0, node.name)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, bool(node.is_folder))
        flags = item.flags() | Qt.ItemFlag.ItemIsDragEnabled
        if node.is_folder:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
            item.setIcon(0, get_cached_icon("📂"))
            item.setForeground(0, QColor(get_folder_color(node.depth)))
        else:
            flags &= ~Qt.ItemFlag.ItemIsDropEnabled
            item.setIcon(0, get_cached_icon("📄"))
            item.setForeground(0, QColor(get_file_color(node.name)))
        item.setFlags(flags)

        if node.comment:
            item.setText(1, node.comment)
            item.setForeground(1, QColor(COMMENT_COLOR))
            comment_font = item.font(1)
            comment_font.setItalic(True)
            item.setFont(1, comment_font)
        return item

    def _make_placeholder(self, node):
        placeholder = QTreeWidgetItem(["Loading…", ""])
        placeholder.setData(0, Qt.ItemDataRole.UserRole, (self._LAZY_TAG, node))
        placeholder.setFlags(
            placeholder.flags()
            & ~Qt.ItemFlag.ItemIsDragEnabled
            & ~Qt.ItemFlag.ItemIsDropEnabled
            & ~Qt.ItemFlag.ItemIsSelectable
        )
        italic = placeholder.font(0)
        italic.setItalic(True)
        placeholder.setFont(0, italic)
        placeholder.setForeground(0, QColor("#8A8A8A"))
        return placeholder

    def _populate_shallow(self, parent_item, parent_node):
        for child in parent_node.children:
            item = self._build_item_for_node(child)
            parent_item.addChild(item)
            if child.is_folder and child.children:
                item.addChild(self._make_placeholder(child))
                # This folder's real children aren't materialized as items
                # yet - only the placeholder stands in for them. Moving
                # this item, or dropping something new into it, right now
                # would silently drop or orphan everything the placeholder
                # represents when the tree gets read back into text, so
                # both are disabled until it's been expanded (see
                # _on_tree_item_expanded, which turns them back on).
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled
                )

    def _populate_eager(self, parent_item, parent_node):
        for child in parent_node.children:
            item = self._build_item_for_node(child)
            parent_item.addChild(item)
            if child.is_folder:
                self._populate_eager(item, child)

    def _on_tree_item_expanded(self, item):
        if item.childCount() != 1:
            return
        placeholder = item.child(0)
        data = placeholder.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == self._LAZY_TAG:
            node = data[1]
            item.removeChild(placeholder)
            self._populate_shallow(item, node)
            # Fully materialized now - safe to drag/drop again.
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)

    # -- Interactive preview editing -------------------------------------
    #
    # The preview tree is editable like a small file explorer: drag an
    # item onto a folder to move it, right-click for New Folder/New File/
    # Rename/Delete, or press Delete with items selected. Every one of
    # these ends the same way - read the tree widget's current shape back
    # into a Node tree, render it to text, and hand that to
    # _commit_tree_edit(), which pushes the *previous* text onto the
    # undo stack and rebuilds the preview fresh from the new text. That
    # keeps the text box the single source of truth even though the edit
    # started as a mouse action, so Deep Dive / Simulate / Create Structure
    # never see anything the preview didn't actually show.

    def _is_placeholder_item(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return isinstance(data, tuple) and data[0] == self._LAZY_TAG

    def _node_from_item(self, item, depth):
        is_folder = bool(item.data(0, Qt.ItemDataRole.UserRole + 1)) or item.childCount() > 0
        comment = item.text(1).strip() or None
        node = Node(name=item.text(0), is_folder=is_folder, depth=depth, comment=comment)
        for i in range(item.childCount()):
            child_item = item.child(i)
            if self._is_placeholder_item(child_item):
                continue
            child_node = self._node_from_item(child_item, depth + 1)
            child_node.parent = node
            node.children.append(child_node)
        return node

    def _compute_text_from_tree(self):
        """Read the preview tree widget's current shape back into text.
        Returns None if there's no real content (nothing to write back)."""
        root_item = self._preview_root_item
        if root_item is None:
            return None
        root = Node(name="", is_folder=True, depth=-1)
        for i in range(root_item.childCount()):
            child_item = root_item.child(i)
            if self._is_placeholder_item(child_item):
                continue
            node = self._node_from_item(child_item, 0)
            node.parent = root
            root.children.append(node)
        if not root.children:
            return ""
        render_style = STYLE_TREE_DIAGRAM if self.tree_style == STYLE_MIXED else self.tree_style
        return render_structure_text(root, render_style)

    def _commit_tree_edit(self, old_text, new_text):
        """Shared committer for every interactive preview edit (drag,
        create, rename, delete, style auto-correction). No-op if nothing
        actually changed."""
        if new_text is None or new_text == old_text:
            return
        if self._pending_typing_baseline is not None:
            self._commit_typing_undo_step()
        # If a typing flush just landed exactly on old_text, that already
        # recorded the step ending here - don't push the same value again
        # as a second, redundant undo entry right behind it.
        if not self._undo_stack or self._undo_stack[-1] != old_text:
            self._undo_stack.append(old_text)
        self._redo_stack.clear()
        self._last_committed_text = new_text
        self._suspend_undo_capture = True
        self.input_text.blockSignals(True)
        self.input_text.setPlainText(new_text)
        self.input_text.blockSignals(False)
        self._suspend_undo_capture = False
        self.update_preview()

    def _snapshot_before_tree_edit(self):
        self._drag_old_text = self.input_text.toPlainText()

    def _on_tree_edited(self):
        old_text = getattr(self, "_drag_old_text", self.input_text.toPlainText())
        new_text = self._compute_text_from_tree()
        if new_text is None:
            self.update_preview()
            return
        self._commit_tree_edit(old_text, new_text)
        self.status_bar.showMessage("Moved in preview")

    def _delete_selected_tree_items(self):
        items = [
            it for it in self.tree_widget.selectedItems()
            if it is not self._preview_root_item and not self._is_placeholder_item(it)
        ]
        if not items:
            return
        # Drop any item whose ancestor is also selected, so removing a
        # folder doesn't also try to remove (and double-count) its children.
        selected_ids = {id(it) for it in items}
        def has_selected_ancestor(it):
            parent = it.parent()
            while parent is not None:
                if id(parent) in selected_ids:
                    return True
                parent = parent.parent()
            return False
        top_level_selected = [it for it in items if not has_selected_ancestor(it)]

        old_text = self.input_text.toPlainText()
        for it in top_level_selected:
            parent = it.parent()
            (parent or self.tree_widget.invisibleRootItem()).removeChild(it)
        new_text = self._compute_text_from_tree()
        count = len(top_level_selected)
        self._commit_tree_edit(old_text, new_text)
        self.status_bar.showMessage(
            f"Deleted {count} item{'s' if count != 1 else ''} from the preview"
        )

    def _target_folder_item(self, item):
        """Given the item that was right-clicked (or None, for empty
        space), return the folder item new children should be created
        under, and whether that's valid right now."""
        if item is None or item is self._preview_root_item:
            return self._preview_root_item
        if self._is_placeholder_item(item):
            return None
        is_folder = bool(item.data(0, Qt.ItemDataRole.UserRole + 1)) or item.childCount() > 0
        return item if is_folder else item.parent()

    def _show_tree_context_menu(self, pos):
        if self._preview_root_item is None:
            return
        item = self.tree_widget.itemAt(pos)
        if item is not None and self._is_placeholder_item(item):
            self.status_bar.showMessage("Expand this folder first")
            return
        target = self._target_folder_item(item)

        menu = QMenu(self)
        act_new_folder = menu.addAction(get_cached_icon("📂", 20), "New Folder")
        act_new_file = menu.addAction(get_cached_icon("📄", 20), "New File…")
        act_rename = act_delete = act_convert = None
        real_item = item if (item is not None and item is not self._preview_root_item) else None
        if real_item is not None:
            menu.addSeparator()
            act_rename = menu.addAction("Rename")
            is_folder = bool(real_item.data(0, Qt.ItemDataRole.UserRole + 1)) or real_item.childCount() > 0
            act_convert = menu.addAction("Convert to File…" if is_folder else "Convert to Folder")
            menu.addSeparator()
            act_delete = menu.addAction("Delete")

        chosen = menu.exec(self.tree_widget.viewport().mapToGlobal(pos))
        if chosen is None or target is None:
            return
        if chosen is act_new_folder:
            self._create_child_item(target, is_folder=True)
        elif chosen is act_new_file:
            self._create_child_item(target, is_folder=False)
        elif act_rename is not None and chosen is act_rename:
            self._rename_item(real_item)
        elif act_convert is not None and chosen is act_convert:
            self._convert_item(real_item)
        elif act_delete is not None and chosen is act_delete:
            self.tree_widget.clearSelection()
            real_item.setSelected(True)
            self.tree_widget.setCurrentItem(real_item)
            self._delete_selected_tree_items()

    def _convert_item(self, item):
        """Flip an item between folder and file. Folder-to-file always
        asks for an extension (folders don't have one); file-to-folder
        asks whether to drop the existing extension, since a folder
        conventionally doesn't have one either. Either popup can just be
        closed/cancelled - that's treated as "leave the name as-is"."""
        is_folder = bool(item.data(0, Qt.ItemDataRole.UserRole + 1)) or item.childCount() > 0
        name = item.text(0)

        if is_folder:
            if item.childCount() == 1 and self._is_placeholder_item(item.child(0)):
                self.status_bar.showMessage(
                    "Expand this folder first so its contents aren't lost in the conversion"
                )
                return
            if item.childCount() > 0:
                reply = QMessageBox.question(
                    self,
                    "Convert to File",
                    f'"{name}" contains {item.childCount()} item(s). Converting it to a '
                    "file will delete all of them. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            ext, ok = QInputDialog.getText(
                self,
                "Convert to File",
                f'"{name}" needs a file extension. Enter one (without the dot), '
                "or close this to leave it without one:",
                text="txt",
            )
            ext = ext.strip().lstrip(".") if ok else ""
            new_name = f"{name}.{ext}" if ext else name

            old_text = self.input_text.toPlainText()
            item.takeChildren()
            item.setText(0, new_name)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            item.setIcon(0, get_cached_icon("📄"))
            item.setForeground(0, QColor(get_file_color(new_name)))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            new_text = self._compute_text_from_tree()
            self._commit_tree_edit(old_text, new_text)
            self.status_bar.showMessage(f"Converted to file: {new_name}")
        else:
            base, dot, ext = name.rpartition(".")
            new_name = name
            if dot and base:
                reply = QMessageBox.question(
                    self,
                    "Convert to Folder",
                    f"Remove the file extension \".{ext}\"?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    new_name = base

            old_text = self.input_text.toPlainText()
            item.setText(0, new_name)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
            item.setIcon(0, get_cached_icon("📂"))
            item.setForeground(0, QColor(get_folder_color(self._item_depth(item))))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            new_text = self._compute_text_from_tree()
            self._commit_tree_edit(old_text, new_text)
            self.status_bar.showMessage(f"Converted to folder: {new_name}")

    def _item_depth(self, item):
        """Depth of an item relative to the project root (the invisible
        "Project Structure" wrapper is depth -1, its direct children are
        depth 0) - only used to pick a sensible folder color for newly
        created items."""
        depth = -1
        node = item
        while node is not None and node is not self._preview_root_item:
            depth += 1
            node = node.parent()
        return depth

    def _create_child_item(self, parent_item, is_folder):
        kind = "Folder" if is_folder else "File"
        default_name = "New Folder" if is_folder else "new_file.txt"
        name, ok = QInputDialog.getText(
            self, f"New {kind}", f"{kind} name:", text=default_name
        )
        if not ok:
            return
        name = name.strip().rstrip("/").strip()
        if not name:
            return

        old_text = self.input_text.toPlainText()
        depth = self._item_depth(parent_item) + 1
        node = Node(name=name, is_folder=is_folder, depth=depth)
        new_item = self._build_item_for_node(node)
        parent_item.addChild(new_item)
        parent_item.setExpanded(True)
        new_text = self._compute_text_from_tree()
        self._commit_tree_edit(old_text, new_text)
        self.status_bar.showMessage(f"Added {kind.lower()}: {name}")

    def _rename_item(self, item):
        if item is None or item is self._preview_root_item:
            return
        current_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current_name)
        if not ok:
            return
        new_name = new_name.strip().rstrip("/").strip()
        if not new_name or new_name == current_name:
            return
        old_text = self.input_text.toPlainText()
        item.setText(0, new_name)
        new_text = self._compute_text_from_tree()
        self._commit_tree_edit(old_text, new_text)
        self.status_bar.showMessage(f"Renamed to: {new_name}")

    # -- Unified undo/redo -------------------------------------------------

    def _on_input_text_changed(self):
        if not self._suspend_undo_capture:
            if self._pending_typing_baseline is None:
                self._pending_typing_baseline = self._last_committed_text
            self._typing_debounce.start()
        self.update_preview()

    def _commit_typing_undo_step(self):
        current = self.input_text.toPlainText()
        if self._pending_typing_baseline is not None and self._pending_typing_baseline != current:
            self._undo_stack.append(self._pending_typing_baseline)
            self._redo_stack.clear()
            self._last_committed_text = current
        self._pending_typing_baseline = None
        # Safety net: catches hand-typed stray tree characters, IME input,
        # or any paste route insertFromMimeData doesn't see. The main path
        # for a Ctrl+V paste is _on_text_pasted, which corrects immediately
        # instead of waiting out this pause.
        self._apply_enforced_style_correction()

    def _on_enforce_toggled(self, _state):
        self.update_preview()
        self._apply_enforced_style_correction()

    def _on_text_pasted(self):
        self._apply_enforced_style_correction()

    def _apply_enforced_style_correction(self):
        """When "Enforce this style" is on, make sure the text actually
        looks like the enforced style instead of just being parsed as if
        it were - e.g. pasting a tree diagram while Plain indented is
        enforced should rewrite it into real plain indentation, not just
        silently treat the │├└ characters as noise while leaving them
        sitting in the box looking like nothing happened. Mixed is left
        alone since it has no single canonical text form to rewrite into."""
        if not self.enforce_style_cb.isChecked() or self.tree_style == STYLE_MIXED:
            return
        text = self.input_text.toPlainText()
        if not text.strip():
            return
        root_node, _ = self._parse(text)
        if not root_node.children:
            return
        corrected = render_structure_text(root_node, self.tree_style)
        if corrected.strip() == text.strip():
            return
        self._commit_tree_edit(text, corrected)
        self.status_bar.showMessage("Auto-corrected text to match the enforced style")

    def _restore_text(self, text):
        self._suspend_undo_capture = True
        self.input_text.blockSignals(True)
        self.input_text.setPlainText(text)
        self.input_text.blockSignals(False)
        self._suspend_undo_capture = False
        self._last_committed_text = text
        self.update_preview()

    def _do_undo(self):
        if self._pending_typing_baseline is not None:
            self._commit_typing_undo_step()
        if not self._undo_stack:
            self.status_bar.showMessage("Nothing to undo")
            return
        current = self.input_text.toPlainText()
        previous = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_text(previous)
        self.status_bar.showMessage(f"Undid last change ({len(self._undo_stack)} more available)")

    def _do_redo(self):
        if not self._redo_stack:
            self.status_bar.showMessage("Nothing to redo")
            return
        current = self.input_text.toPlainText()
        next_text = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_text(next_text)
        self.status_bar.showMessage(f"Redid change ({len(self._redo_stack)} more available)")

    def eventFilter(self, obj, event):
        if obj is self.input_text and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Undo):
                self._do_undo()
                return True
            if event.matches(QKeySequence.StandardKey.Redo):
                self._do_redo()
                return True
        return super().eventFilter(obj, event)

    def _ignore_connectors(self):
        """True only when the user has explicitly locked in Plain indented
        via the Enforce checkbox - the one case where tree-diagram glyphs
        (│├└) in the text should be treated as plain noise instead of
        structural signals."""
        return self.enforce_style_cb.isChecked() and self.tree_style == STYLE_PLAIN_INDENT

    def _smart_mixed(self):
        """True when the current style is Mixed (auto-detected, or
        manually picked from the dropdown) - the only case where bare
        tree connectors get resolved relative to context instead of
        taken at face value."""
        return self.tree_style == STYLE_MIXED

    def _parse(self, text):
        """Single place every call site parses input text from, so the
        Enforce checkbox and Mixed-style handling can never drift out of
        sync between the preview, Deep Dive, Simulate, and actual creation."""
        return parse_structure(
            text,
            ignore_connectors=self._ignore_connectors(),
            smart_mixed=self._smart_mixed(),
        )

    def _sync_style_dropdown(self, structure):
        """Auto-detect how the currently typed/pasted text is formatted
        and update the Tree style dropdown to match - unless the user has
        checked "Enforce tree style", in which case their manual choice
        always wins and auto-detection is skipped entirely."""
        if self.enforce_style_cb.isChecked():
            return None
        detected = detect_structure_style(structure)
        if detected is None or detected == self.tree_style:
            return detected
        self.tree_style = detected
        idx = self.tree_style_combo.findData(detected)
        if idx != -1:
            self.tree_style_combo.blockSignals(True)
            self.tree_style_combo.setCurrentIndex(idx)
            self.tree_style_combo.blockSignals(False)
        return detected

    def update_preview(self):
        structure = self.input_text.toPlainText().strip()
        self.tree_widget.clear()
        self._preview_root_item = None

        if not structure:
            self.tree_diagram_detected = False
            return

        detected_style = self._sync_style_dropdown(structure)
        self.tree_diagram_detected = any(char in structure for char in ["├", "│", "└"])

        root_node, indent_unit = self._parse(structure)
        total_nodes = count_nodes(root_node)

        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, "Project Structure")
        root_item.setIcon(0, get_cached_icon("📁"))
        # The wrapper node itself can't be dragged or deleted, but items
        # CAN be dropped directly onto it to become top-level project items.
        root_item.setFlags(
            (root_item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            & ~Qt.ItemFlag.ItemIsDragEnabled
            & ~Qt.ItemFlag.ItemIsSelectable
        )
        self._preview_root_item = root_item

        if total_nodes > LAZY_LOAD_THRESHOLD:
            self._populate_shallow(root_item, root_node)
            root_item.setExpanded(True)
        else:
            self._populate_eager(root_item, root_node)
            self.tree_widget.expandAll()

        self.tree_widget.resizeColumnToContents(0)
        if self.tree_widget.columnWidth(1) < 160:
            self.tree_widget.setColumnWidth(1, 220)

        if total_nodes > LAZY_LOAD_THRESHOLD:
            self.status_bar.showMessage(
                f"Ready. {total_nodes:,} items - expand a folder in the preview to load it."
            )
        elif detected_style == STYLE_MIXED:
            self.status_bar.showMessage(
                "Mixed formatting detected (tree connectors + plain indenting together) - "
                "nesting shown is best-effort. Check the preview, or pick Tree diagram / "
                "Plain indented above to normalize the text."
            )
        elif self.tree_diagram_detected:
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
        root_node, _ = self._parse(text)
        if not root_node.children:
            QMessageBox.information(
                self, "Nothing to show", "No valid folders or files were found in the input."
            )
            return
        total_nodes = count_nodes(root_node)
        if total_nodes > 4000:
            proceed = QMessageBox.question(
                self,
                "Large Structure",
                f"This structure has {total_nodes:,} items. Deep Dive builds one row per "
                "item, so this may take a moment. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if proceed != QMessageBox.StandardButton.Yes:
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
            self._ignore_connectors(),
            self._smart_mixed(),
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
        root_node, _ = self._parse(text)
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

    def import_folder(self):
        """Scan a real folder on disk and turn it into a project structure
        ::the other direction from Create Structure. Scanning runs on a
        background thread (FolderScanWorker) so importing a large folder
        never freezes the window."""
        if self.scan_worker is not None:
            return  # a scan is already running

        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Import", "", QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return

        self.import_folder_btn.setEnabled(False)
        self.create_btn.setEnabled(False)
        self.simulate_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # indeterminate - item count isn't known up front
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(f"Scanning {folder} ...")

        self.scan_worker = FolderScanWorker(folder)
        self.scan_worker.progress.connect(
            lambda n: self.status_bar.showMessage(f"Scanning {folder} ... {n:,} items")
        )
        self.scan_worker.completed.connect(self.on_scan_completed)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.finished.connect(self._reset_scan_ui)
        self.scan_worker.start()

    def on_scan_completed(self, payload):
        wrapper_root, count = payload
        text = render_structure_text(wrapper_root, self.tree_style)
        self.input_text.setPlainText(text)

        top = wrapper_root.children[0] if wrapper_root.children else None
        if top is not None:
            root_path = os.path.dirname(self.scan_worker.folder_path) if self.scan_worker else ""
            if root_path:
                if self.folder_combo.findText(root_path) == -1:
                    self.folder_combo.insertItem(0, root_path)
                self.folder_combo.setCurrentText(root_path)

        self.status_bar.showMessage(f"Imported {count:,} item(s) from folder.")

    def on_scan_error(self, message):
        QMessageBox.warning(self, "Import Folder", message)
        self.status_bar.showMessage("Folder import failed.")

    def _reset_scan_ui(self):
        self.import_folder_btn.setEnabled(True)
        self.create_btn.setEnabled(True)
        self.simulate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.scan_worker = None

    def on_tree_style_changed(self, _index):
        """Re-renders whatever structure is currently loaded in the
        chosen style, so the toggle applies immediately instead of only
        affecting the next import/preset."""
        self.tree_style = self.tree_style_combo.currentData()
        text = self.input_text.toPlainText().strip()
        if not text:
            return
        root_node, _ = self._parse(text)
        if not root_node.children:
            return
        rendered = render_structure_text(root_node, self.tree_style)
        self.input_text.blockSignals(True)
        self.input_text.setPlainText(rendered)
        self.input_text.blockSignals(False)
        self.update_preview()

    def load_selected_preset(self, _index=None):
        name = self.preset_combo.currentText()
        if name not in PRESET_STRUCTURES:
            return
        root_node, _ = parse_structure(PRESET_STRUCTURES[name])
        text = render_structure_text(root_node, self.tree_style)
        self.input_text.setPlainText(text)
        self.status_bar.showMessage(f"Loaded preset: {name}")

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
        self.input_text.setPlainText(SAMPLE_STRUCTURE)
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
                self._ignore_connectors(),
                self._smart_mixed(),
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
                <p><strong>Version 4.0</strong></p>
                <p>Turn a real folder into a project structure, or a project structure into real folders.</p>

                <p><strong> Features:</strong></p>
                <ul>
                    <li> Import Folder - scan any real folder on disk into an editable project structure</li>
                    <li> Three tree styles - Tree diagram, Plain indented, and auto-detected Mixed - the dropdown switches itself to match what you type</li>
                    <li> "Enforce this style" checkbox to lock the style and stop auto-detection when you need to</li>
                    <li> Interactive preview - drag items to move them, right-click to add/rename/convert/delete, Delete key removes a selection</li>
                    <li> VS Code-style multi-cursor editing in the text box (Alt+click, Alt+Shift+click, Alt+Up/Down, Alt+Shift+Up/Down) - see Help &gt; Shortcuts</li>
                    <li> Unlimited undo/redo (Ctrl+Z / Ctrl+Y) covering typing and every preview edit alike</li>
                    <li> Ready-made presets for common project types</li>
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
        <h1>Working With Project Structures</h1>
        <p>FolderSmith Pro works in both directions: turn a real folder into a
        project structure with <b>Import Folder</b>, or type/paste a structure
        and click <b>Create Structure</b> to build the real folders and files.</p>

        <h2>Import Folder</h2>
        <p>Click <b>Import Folder…</b> to scan any real folder on disk (any
        project type) and turn it straight into an editable structure. Large
        folders are scanned on a background thread and the preview loads
        folders on demand, so importing a big folder never freezes the app.</p>

        <h2>Tree Style</h2>
        <p>The <b>Tree style</b> dropdown shows how a structure is written -
        as a connector-style tree diagram (├── └──), as plain indented text,
        or <b>Mixed</b>, which means the two are combined in what you typed.
        It switches itself automatically to match whatever you type or
        paste, so you don't have to set it by hand. Pick a style from the
        dropdown yourself at any time to reformat the current text into it.</p>

        <p>If you'd rather the dropdown stopped auto-switching - for example
        you're typing plain indentation but your text happens to contain
        stray ├ └ │ characters - tick <b>Enforce this style</b> next to it.
        With Enforce on and Plain indented selected, any tree characters in
        the text are treated as ordinary text, never as structure.</p>

        <p>For <b>Mixed</b> text, nesting is resolved as best as it
        reasonably can be from the connectors and indentation present, but
        a line with absolutely no indentation and no connector carries no
        nesting information at all - guessing there would be wrong as often
        as it's right, so those lines stay at the top level rather than a
        confident-looking guess. Add a bit of indentation or a connector to
        any line that needs to nest, and it will always place correctly.</p>

        <h2>Interactive Preview</h2>
        <p>The Structure Preview on the right isn't just a read-only view -
        it works like a small file explorer:</p>
        <ul>
            <li><b>Drag</b> a file or folder onto another folder to move it
            there. Drop it on empty space, or on the "Project Structure"
            heading at the top, to make it a top-level item.</li>
            <li><b>Right-click</b> anywhere for <b>New Folder</b> or
            <b>New File…</b> (type any name, with any extension you like).
            Right-click an existing item for <b>Rename</b> or
            <b>Delete</b> as well.</li>
            <li>Select one or more items and press <b>Delete</b> to remove
            them.</li>
        </ul>
        <p>Every one of these updates the text on the left immediately -
        the preview and the text always describe the same structure.</p>

        <h2>Undo / Redo</h2>
        <p><b>Ctrl+Z</b> and <b>Ctrl+Y</b> (or the ↩ / ↪ buttons above the
        preview) undo and redo typing and interactive preview edits alike,
        as one shared history with no limit on how far back you can go.
        Typing is grouped into one undo step per pause, the way any text
        editor does it; each drag, create, rename, or delete is its own
        step.</p>

        <h2>Presets</h2>
        <p>Pick a ready-made layout from the <b>Preset</b> dropdown for common
        project types - no internet connection needed.</p>

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

    def show_shortcuts(self):
        shortcuts_text = """
        <html>
        <center>
        <h1>Shortcuts</h1>

        <h2>Undo / Redo</h2>
        <table style="margin:0 auto;" cellpadding="4">
        <tr><td><b>Ctrl+Z</b></td><td>Undo - typing and preview edits alike</td></tr>
        <tr><td><b>Ctrl+Y</b></td><td>Redo</td></tr>
        </table>

        <h2>Editing (in the structure text box)</h2>
        <table style="margin:0 auto;" cellpadding="4">
        <tr><td><b>Alt+Click</b></td><td>Add a secondary cursor - click an existing one again to remove it</td></tr>
        <tr><td><b>Alt+Shift+Click</b></td><td>Add a column of cursors from the current line to the clicked line/column</td></tr>
        <tr><td><b>Esc</b></td><td>Clear all secondary cursors</td></tr>
        <tr><td><b>Alt+Up / Alt+Down</b></td><td>Move the current line up/down</td></tr>
        <tr><td><b>Alt+Shift+Up / Alt+Shift+Down</b></td><td>Duplicate the current line up/down</td></tr>
        <tr><td><b>Home</b></td><td>First press: first non-whitespace character. Press again: column 0</td></tr>
        </table>

        <h2>Structure Preview</h2>
        <table style="margin:0 auto;" cellpadding="4">
        <tr><td><b>Drag &amp; drop</b></td><td>Move a file/folder to a new parent</td></tr>
        <tr><td><b>Right-click</b></td><td>New Folder, New File, Rename, Convert, Delete</td></tr>
        <tr><td><b>Delete</b></td><td>Remove the selected item(s)</td></tr>
        </table>

        <h2>Other</h2>
        <table style="margin:0 auto;" cellpadding="4">
        <tr><td><b>Ctrl+I</b></td><td>Import Folder</td></tr>
        <tr><td><b>Ctrl+Shift+C</b></td><td>Clear</td></tr>
        </table>

        <p style="max-width:460px;margin:16px auto 0;color:#aaa;font-size:12px;">
        Multi-cursor editing works on carets, not highlighted column
        selections - each Alt-click/Alt-Shift-click spot is a place to
        type, not a block of selected text.
        </p>
        </center>
        </html>
        """
        msg = ModernMessageBox(self)
        msg.setWindowTitle("Shortcuts")
        msg.setText(shortcuts_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def closeEvent(self, event):
        if self.structure_worker and self.structure_worker.isRunning():
            self.structure_worker.cancel()
            self.structure_worker.wait(1000)

        if self.zip_worker and self.zip_worker.isRunning():
            self.zip_worker.cancel()
            self.zip_worker.wait(1000)

        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.cancel()
            self.scan_worker.wait(1000)

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