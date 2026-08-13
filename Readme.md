# 📁 FolderSmith Pro

Create entire project folder and file structures from a single pasted block of text — no clicking through dozens of "New Folder" dialogs. Paste a plain-indented list or an ASCII tree diagram, preview it live, and generate the real thing on disk (or export it straight to a ZIP).

![FolderSmith Pro screenshot](app.png)

##  Features

-  **Paste-to-structure** — turn a plain-text outline into real folders and files in one click
-  **Smart tree-diagram parsing** — paste ASCII tree diagrams (`├──`, `│`, `└──`) directly, symbols are handled automatically
-  **Multi-language comment extraction** — strips trailing comments in `#`, `//`, `/* */`, `<!-- -->`, `--`, `;`, and `%` styles so they don't end up in file/folder names
-  **Live preview** that always matches exactly what gets created
-  **Deep Dive view** — a searchable, flattened table of every folder and file before you commit
- ✔ **On-disk verification** after creation, so you know nothing silently failed
-  **Export to ZIP** instead of writing to disk
-  Color-coded syntax highlighting by file type

##  Requirements

- Python 3.9+
- [PyQt6](https://pypi.org/project/PyQt6/)

```bash
pip install PyQt6
```

##  Usage

```bash
python foldersmith.py
```

1. Paste your project structure into the input box (see format below).
2. Check the live preview on the right — it shows exactly what will be created.
3. Optionally open **Tools → Deep Dive** for a full breakdown table.
4. Click **Create Structure** to generate it on disk, or export it as a ZIP.

##  Structure Format

| Element | Syntax | Example |
|---|---|---|
| Folder | Ends with `/` | `src/` |
| File | No trailing slash | `main.py` |
| Nesting | Indent with spaces | `  utils/` |
| Comments | `#` `//` `/* */` `<!-- -->` `--` `;` `%` | `main.py  # entry point` |

Tree diagrams pasted from `tree` output or similar tools are also supported and parsed automatically.

### Sample project structure

```
my-app/
├── app/
│   ├── main.py             # Entry point of the app
│   ├── utils/
│   │   └── helpers.py
│   └── config.py
├── tests/
│   ├── test_main.py
│   └── test_helpers.py
├── assets/
│   └── logo.png
├── .gitignore
├── requirements.txt
└── README.md
```

Paste that block (or your own) into FolderSmith Pro and it will build the matching folders and files for you.

## 📸 Output

![FolderSmith Pro output example](output.png)

*(Drop your `output.png` or `output.jpg` screenshot into this folder — either extension works with the image link above.)*

##  Support & Contact

- Email: [studiocoding09@gmail.com](mailto:studiocoding09@gmail.com)
- Support: (https://chibuikeonuigbo.github.io/Support_Page/)

##  License

© 2025 FolderSmith Pro. All rights reserved.