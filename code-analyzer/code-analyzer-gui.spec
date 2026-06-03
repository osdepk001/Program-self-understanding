# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

added_files = [
    ("config.yaml", "."),
    ("src/images/os.ico", "src/images"),
]

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

qfluentwidgets_imports = collect_submodules("qfluentwidgets")
qfluentwidgets_datas = collect_data_files("qfluentwidgets", subdir="", includes=["**/*.ttf", "**/*.png", "**/*.svg", "**/*.qss"])

a = Analysis(
    ["run_gui.py"],
    pathex=[],
    binaries=[],
    datas=added_files + qfluentwidgets_datas,
    hiddenimports=[
        "src",
        "src.main",
        "src.gui_app",
        "src.parser",
        "src.parser.python_parser",
        "src.parser.js_parser",
        "src.parser.generic_parser",
        "src.analyzer",
        "src.analyzer.llm_client",
        "src.analyzer.incremental_cache",
        "src.analyzer.rule_engine",
        "src.graph",
        "src.graph.dependency_graph",
        "src.reporter",
        "src.reporter.json_reporter",
        "src.reporter.markdown_reporter",
        "src.reporter.html_reporter",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
        "qfluentwidgets",
        "darkdetect",
        *qfluentwidgets_imports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "regex", "_regex", "tkinter", "sv_ttk",
        "torch", "functorch", "scipy", "sympy", "einops",
        "numpy", "numpy.core", "numpy.f2py", "numpy.char", "numpy.rec",
        "numpy.ctypeslib", "numpy.fft", "numpy.strings",
        "PIL", "PIL.Image", "PIL.ImageFilter",
        "networkx", "matplotlib",
        "pandas", "sklearn", "scikit",
        "jupyter", "ipython", "notebook",
        "tensorflow", "keras",
        "transformers", "tokenizers",
        "cv2", "opencv",
        "django", "flask", "fastapi",
        "sqlalchemy",
        "fsspec", "tqdm", "zstandard",
        "certifi", "requests", "charset_normalizer",
        "urllib3", "urllib3.contrib",
        "setuptools", "setuptools._vendor",
        "distutils", "_distutils_hack",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="code-analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="src/images/os.ico",
)