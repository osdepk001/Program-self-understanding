from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


LANG_CONFIG = {
    "go": {
        "extensions": {".go"},
        "single_import": re.compile(r'import\s+(?:\w+\s+)?\"([^\"]+)\"'),
        "multi_import": re.compile(r'import\s*\(\s*((?:\s*(?:\w+\s+)?\"[^\"]+\"\s*)+)\s*\)'),
        "inner_import": re.compile(r'(?:\w+\s+)?\"([^\"]+)\"'),
    },
    "rust": {
        "extensions": {".rs"},
        "use_import": re.compile(r'use\s+((?:crate|self|super)(?:::\w+)*)(?:::[\{\*][^;]*)?;'),
        "mod_decl": re.compile(r'(?:pub\s+)?mod\s+(\w+)\s*;'),
        "extern_crate": re.compile(r'extern\s+crate\s+(\w+)\s*;'),
    },
    "java": {
        "extensions": {".java"},
        "import_single": re.compile(r'import\s+((?:static\s+)?[\w.]+(?:\.[A-Z]\w*)*)\s*;'),
        "package_decl": re.compile(r'package\s+([\w.]+)\s*;'),
    },
    "php": {
        "extensions": {".php"},
        "require": re.compile(r'require(_once)?\s*\(?[\'"]([^\'"]+)[\'"]\)?'),
        "include": re.compile(r'include(_once)?\s*\(?[\'"]([^\'"]+)[\'"]\)?'),
        "use_namespace": re.compile(r'use\s+([\w\\]+)(?:\s+as\s+\w+)?;'),
    },
    "c": {
        "extensions": {".c", ".h"},
        "include": re.compile(r'#include\s+[<\"]([^>\"]+)[>\"]'),
    },
    "cpp": {
        "extensions": {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"},
        "include": re.compile(r'#include\s+[<\"]([^>\"]+)[>\"]'),
    },
    "csharp": {
        "extensions": {".cs"},
        "using": re.compile(r'using\s+(?:static\s+)?([\w.]+)\s*;'),
    },
    "ruby": {
        "extensions": {".rb"},
        "require": re.compile(r'require\s+[\'"]([^\'"]+)[\'"]'),
        "require_relative": re.compile(r'require_relative\s+[\'"]([^\'"]+)[\'"]'),
        "load": re.compile(r'load\s+[\'"]([^\'"]+)[\'"]'),
    },
    "kotlin": {
        "extensions": {".kt", ".kts"},
        "import_single": re.compile(r'import\s+([\w.]+)'),
    },
    "swift": {
        "extensions": {".swift"},
        "import_single": re.compile(r'import\s+(\w+)'),
    },
    "lua": {
        "extensions": {".lua"},
        "require": re.compile(r'require\s*\(?\s*[\'"]([^\'"]+)[\'"]'),
        "dofile": re.compile(r'dofile\s*\(?\s*[\'"]([^\'"]+)[\'"]'),
    },
    "shell": {
        "extensions": {".sh", ".bash", ".zsh"},
        "source": re.compile(r'(?:source|\.)\s+[\'"]?([^\s;\'"]+)[\'"]?'),
    },
    "dart": {
        "extensions": {".dart"},
        "import_single": re.compile(r'import\s+[\'"](package:[^\'"]+|dart:[^\'"]+)[\'"]'),
        "import_part": re.compile(r'part\s+[\'"]([^\'"]+)[\'"]'),
        "part_of": re.compile(r'part\s+of\s+[\'"]([^\'"]+)[\'"]'),
    },
    "scala": {
        "extensions": {".scala"},
        "import_single": re.compile(r'import\s+([\w.]+)'),
    },
    "perl": {
        "extensions": {".pl", ".pm"},
        "use": re.compile(r'use\s+([\w:]+)'),
        "require": re.compile(r'require\s+([\w:]+)'),
    },
    "elixir": {
        "extensions": {".ex", ".exs"},
        "import": re.compile(r'(?:import|alias)\s+([\w.]+)'),
        "require": re.compile(r'require\s+([\w.]+)'),
    },
    "haskell": {
        "extensions": {".hs", ".lhs"},
        "import": re.compile(r'import\s+(?:qualified\s+)?([\w.]+)'),
    },
    "zig": {
        "extensions": {".zig"},
        "import": re.compile(r'@import\s*\(\s*\"([^\"]+)\"\s*\)'),
    },
    "rlang": {
        "extensions": {".r", ".R"},
        "source": re.compile(r'source\s*\(\s*[\'"]([^\'"]+)[\'"]'),
        "library": re.compile(r'library\s*\(\s*([\w.]+)\s*\)'),
    },
    "groovy": {
        "extensions": {".groovy"},
        "import_single": re.compile(r'import\s+(?:static\s+)?([\w.]+)'),
    },
    "objective_c": {
        "extensions": {".m", ".mm"},
        "include": re.compile(r'#include\s+[<\"]([^>\"]+)[>\"]'),
        "import": re.compile(r'#import\s+[<\"]([^>\"]+)[>\"]'),
    },
    "nim": {
        "extensions": {".nim"},
        "import": re.compile(r'import\s+([\w/]+)'),
        "include": re.compile(r'include\s+([\w/]+)'),
    },
    "clojure": {
        "extensions": {".clj", ".cljs", ".cljc", ".edn"},
        "require": re.compile(r'\(require\s+[\'\[][\s\w.\-:/]+'),
        "ns_require": re.compile(r'\(ns\s+[\w.\-]+\s+\(:require\s+[\s\w.\-:/\[\]]+\)'),
    },
    "erlang": {
        "extensions": {".erl", ".hrl"},
        "include": re.compile(r'-include\s*\(\s*\"([^\"]+)\"\s*\)'),
        "include_lib": re.compile(r'-include_lib\s*\(\s*\"([^\"]+)\"\s*\)'),
        "import": re.compile(r'-import\s*\(\s*[\w.]+,\s*\[[\w\s,/]+\]\s*\)'),
    },
    "erlang_header": {
        "extensions": {".hrl"},
        "include": re.compile(r'-include\s*\(\s*\"([^\"]+)\"\s*\)'),
        "include_lib": re.compile(r'-include_lib\s*\(\s*\"([^\"]+)\"\s*\)'),
    },
    "solidity": {
        "extensions": {".sol"},
        "import": re.compile(r'import\s+[\'"]([^\'"]+)[\'"]'),
        "import_from": re.compile(r'import\s+\{[^}]+\}\s+from\s+[\'"]([^\'"]+)[\'"]'),
    },
}

LANG_EXPORT_PATTERNS = {
    "go": [
        (re.compile(r'func\s+([A-Z]\w*)\s*\('), "fn"),
        (re.compile(r'type\s+([A-Z]\w*)\s+struct\s*\{'), "class"),
        (re.compile(r'type\s+([A-Z]\w*)\s+interface\s*\{'), "class"),
    ],
    "rust": [
        (re.compile(r'pub\s+fn\s+(\w+)\s*\('), "fn"),
        (re.compile(r'pub\s+struct\s+(\w+)'), "class"),
        (re.compile(r'pub\s+enum\s+(\w+)'), "class"),
        (re.compile(r'pub\s+trait\s+(\w+)'), "class"),
        (re.compile(r'pub\s+mod\s+(\w+)'), "mod"),
    ],
    "java": [
        (re.compile(r'public\s+(?:abstract\s+)?(?:static\s+)?class\s+(\w+)'), "class"),
        (re.compile(r'public\s+(?:static\s+)?interface\s+(\w+)'), "class"),
        (re.compile(r'public\s+(?:static\s+)?\w+(?:<[^>]+>)?\s+(\w+)\s*\('), "fn"),
    ],
    "php": [
        (re.compile(r'function\s+(\w+)\s*\('), "fn"),
        (re.compile(r'class\s+(\w+)'), "class"),
        (re.compile(r'interface\s+(\w+)'), "class"),
        (re.compile(r'trait\s+(\w+)'), "class"),
    ],
    "c": [
        (re.compile(r'^(?:static\s+)?(?:inline\s+)?\w+\s+(\w+)\s*\([^)]*\)\s*\{'), "fn"),
        (re.compile(r'typedef\s+(?:struct|enum|union)\s*(?:\w+\s*)?\{'), "class"),
        (re.compile(r'struct\s+(\w+)\s*\{'), "class"),
        (re.compile(r'enum\s+(\w+)\s*\{'), "class"),
        (re.compile(r'union\s+(\w+)\s*\{'), "class"),
    ],
    "cpp": [
        (re.compile(r'(?:virtual\s+)?(?:static\s+)?(?:inline\s+)?\w+(?:<[^>]+>)?\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?\{'), "fn"),
        (re.compile(r'(?:class|struct)\s+(\w+)(?:\s*:\s*public\s+\w+)?\s*\{'), "class"),
        (re.compile(r'enum\s+(?:class\s+)?(\w+)\s*\{'), "class"),
        (re.compile(r'namespace\s+(\w+)\s*\{'), "mod"),
    ],
    "csharp": [
        (re.compile(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?\w+(?:<[^>]+>)?\s+(\w+)\s*\('), "fn"),
        (re.compile(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:abstract\s+)?(?:partial\s+)?class\s+(\w+)'), "class"),
        (re.compile(r'(?:public|private|protected|internal)\s+interface\s+(\w+)'), "class"),
        (re.compile(r'(?:public|private|protected|internal)\s+enum\s+(\w+)'), "class"),
        (re.compile(r'(?:public|private|protected|internal)\s+struct\s+(\w+)'), "class"),
        (re.compile(r'namespace\s+([\w.]+)'), "mod"),
    ],
    "ruby": [
        (re.compile(r'def\s+(\w+)'), "fn"),
        (re.compile(r'class\s+(\w+)'), "class"),
        (re.compile(r'module\s+(\w+)'), "mod"),
    ],
    "kotlin": [
        (re.compile(r'fun\s+(\w+)\s*\('), "fn"),
        (re.compile(r'(?:data\s+)?class\s+(\w+)'), "class"),
        (re.compile(r'interface\s+(\w+)'), "class"),
        (re.compile(r'object\s+(\w+)'), "class"),
        (re.compile(r'enum\s+class\s+(\w+)'), "class"),
        (re.compile(r'sealed\s+(?:class|interface)\s+(\w+)'), "class"),
    ],
    "swift": [
        (re.compile(r'func\s+(\w+)\s*\('), "fn"),
        (re.compile(r'class\s+(\w+)'), "class"),
        (re.compile(r'struct\s+(\w+)'), "class"),
        (re.compile(r'protocol\s+(\w+)'), "class"),
        (re.compile(r'enum\s+(\w+)'), "class"),
        (re.compile(r'extension\s+(\w+)'), "class"),
        (re.compile(r'actor\s+(\w+)'), "class"),
    ],
    "lua": [
        (re.compile(r'(?:local\s+)?function\s+(\w+)\s*\('), "fn"),
        (re.compile(r'(\w+)\s*=\s*\{\s*\}'), "class"),
    ],
    "shell": [
        (re.compile(r'function\s+(\w+)\s*\{'), "fn"),
        (re.compile(r'(\w+)\s*\(\s*\)\s*\{'), "fn"),
    ],
    "dart": [
        (re.compile(r'(?:static\s+)?\w+(?:<[^>]+>)?\s+(\w+)\s*\('), "fn"),
        (re.compile(r'(?:abstract\s+)?class\s+(\w+)'), "class"),
        (re.compile(r'mixin\s+(\w+)'), "class"),
        (re.compile(r'extension\s+(\w+)'), "class"),
        (re.compile(r'enum\s+(\w+)'), "class"),
    ],
    "scala": [
        (re.compile(r'def\s+(\w+)\s*\('), "fn"),
        (re.compile(r'(?:abstract\s+)?(?:case\s+)?class\s+(\w+)'), "class"),
        (re.compile(r'object\s+(\w+)'), "class"),
        (re.compile(r'trait\s+(\w+)'), "class"),
        (re.compile(r'enum\s+(\w+)'), "class"),
    ],
    "perl": [
        (re.compile(r'sub\s+(\w+)\s*\{'), "fn"),
        (re.compile(r'package\s+([\w:]+)\s*;'), "class"),
    ],
    "elixir": [
        (re.compile(r'def\s+(\w+)\s*\('), "fn"),
        (re.compile(r'defp\s+(\w+)\s*\('), "fn"),
        (re.compile(r'defmodule\s+([\w.]+)\s+do'), "mod"),
        (re.compile(r'defprotocol\s+([\w.]+)\s+do'), "class"),
        (re.compile(r'defstruct\s+([\w.]+)\s+do'), "class"),
    ],
    "haskell": [
        (re.compile(r'^(\w+)\s*::'), "fn"),
        (re.compile(r'^(\w+)\s+[\w\s]+\s*='), "fn"),
        (re.compile(r'data\s+(\w+)'), "class"),
        (re.compile(r'newtype\s+(\w+)'), "class"),
        (re.compile(r'class\s+(\w+)'), "class"),
        (re.compile(r'type\s+(\w+)'), "class"),
    ],
    "zig": [
        (re.compile(r'pub\s+fn\s+(\w+)\s*\('), "fn"),
        (re.compile(r'fn\s+(\w+)\s*\('), "fn"),
        (re.compile(r'pub\s+const\s+(\w+)\s*=\s*struct'), "class"),
        (re.compile(r'pub\s+const\s+(\w+)\s*=\s*enum'), "class"),
    ],
    "rlang": [
        (re.compile(r'(\w+)\s*<-\s*function\s*\('), "fn"),
        (re.compile(r'setClass\s*\(\s*\"(\w+)\"'), "class"),
        (re.compile(r'setRefClass\s*\(\s*\"(\w+)\"'), "class"),
    ],
    "groovy": [
        (re.compile(r'def\s+(\w+)\s*\('), "fn"),
        (re.compile(r'(?:static\s+)?\w+\s+(\w+)\s*\('), "fn"),
        (re.compile(r'class\s+(\w+)'), "class"),
        (re.compile(r'interface\s+(\w+)'), "class"),
        (re.compile(r'trait\s+(\w+)'), "class"),
        (re.compile(r'enum\s+(\w+)'), "class"),
    ],
    "objective_c": [
        (re.compile(r'[-+]\s*\(\s*\w+\s*(?:\*|\s*)\s*\)\s*(\w+)'), "fn"),
        (re.compile(r'@interface\s+(\w+)'), "class"),
        (re.compile(r'@implementation\s+(\w+)'), "class"),
        (re.compile(r'@protocol\s+(\w+)'), "class"),
    ],
    "nim": [
        (re.compile(r'proc\s+(\w+)\s*\('), "fn"),
        (re.compile(r'func\s+(\w+)\s*\('), "fn"),
        (re.compile(r'type\s+(\w+)\s*=\s*object'), "class"),
        (re.compile(r'type\s+(\w+)\s*=\s*ref\s+object'), "class"),
        (re.compile(r'type\s+(\w+)\s*=\s*enum'), "class"),
    ],
    "clojure": [
        (re.compile(r'\(defn\s+([\w\-?!]+)'), "fn"),
        (re.compile(r'\(defn-\s+([\w\-?!]+)'), "fn"),
        (re.compile(r'\(defrecord\s+([\w\-?!]+)'), "class"),
        (re.compile(r'\(deftype\s+([\w\-?!]+)'), "class"),
        (re.compile(r'\(defprotocol\s+([\w\-?!]+)'), "class"),
    ],
    "erlang": [
        (re.compile(r'^-?spec\s+(\w+)\s*\('), "fn"),
        (re.compile(r'^(\w+)\s*\('), "fn"),
        (re.compile(r'^-record\s*\(\s*(\w+)'), "class"),
    ],
    "solidity": [
        (re.compile(r'function\s+(\w+)\s*\('), "fn"),
        (re.compile(r'contract\s+(\w+)'), "class"),
        (re.compile(r'interface\s+(\w+)'), "class"),
        (re.compile(r'library\s+(\w+)'), "class"),
        (re.compile(r'struct\s+(\w+)'), "class"),
        (re.compile(r'enum\s+(\w+)'), "class"),
        (re.compile(r'event\s+(\w+)\s*\('), "fn"),
    ],
}

COMMENT_PATTERN = re.compile(r'//.*$|#.*$|/\*[\s\S]*?\*/|<!--[\s\S]*?-->|%\{[\s\S]*?%\}|--[\s\S]*?$|\(\*[\s\S]*?\*\)|\{-[\s\S]*?-\}', re.MULTILINE)


class GenericParser:
    """基于正则表达式的多语言解析器，支持 Go、Rust、Java、PHP、C/C++、C#、Ruby、Kotlin、Swift、Lua、Shell、Dart、Scala、Perl、Elixir、Haskell、Zig、R、Groovy、Objective-C、Nim、Clojure、Erlang、Solidity。"""

    def __init__(self, project_root: str) -> None:
        self._project_root = Path(project_root).resolve()

    def parse_file(self, file_path: str, lang: str) -> Optional[FileNode]:
        abs_path = Path(file_path).resolve()
        if not abs_path.exists() or lang not in LANG_CONFIG:
            return None

        try:
            source_code = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

        config = LANG_CONFIG[lang]
        cleaned = COMMENT_PATTERN.sub("", source_code)

        imports = self._extract_imports(cleaned, lang, config, abs_path)
        exports = self._extract_exports(cleaned, lang)
        purpose = self._extract_purpose(cleaned, lang)
        cross_refs = self._extract_cross_refs(cleaned, lang, config, abs_path)

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language=lang,
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
            cross_refs=cross_refs,
            lines=len(source_code.splitlines()),
        )

    def _extract_imports(self, source: str, lang: str, config: dict, source_path: Path) -> list[str]:
        imports: list[str] = []

        if lang == "go":
            for match in config["single_import"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_go_import(module, source_path)
                if resolved:
                    imports.append(resolved)

            for match in config["multi_import"].finditer(source):
                block = match.group(1)
                for inner in config["inner_import"].finditer(block):
                    module = inner.group(1)
                    resolved = self._resolve_go_import(module, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "rust":
            for match in config["use_import"].finditer(source):
                module_path = match.group(1)
                resolved = self._resolve_rust_import(module_path, source_path)
                if resolved:
                    imports.append(resolved)

            for match in config["mod_decl"].finditer(source):
                module_name = match.group(1)
                candidate = self._project_root / source_path.parent.relative_to(self._project_root) / f"{module_name}.rs"
                resolved = self._to_relative(candidate)
                if resolved:
                    imports.append(resolved)
                candidate = self._project_root / source_path.parent.relative_to(self._project_root) / module_name / "mod.rs"
                if candidate.exists():
                    resolved = self._to_relative(candidate)
                    if resolved:
                        imports.append(resolved)

        elif lang == "java":
            for match in config["import_single"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_java_import(module, source_path)
                if resolved:
                    imports.append(resolved)

        elif lang == "php":
            for pattern_key in ("require", "include"):
                for match in config[pattern_key].finditer(source):
                    included = match.group(2)
                    resolved = self._resolve_php_include(included, source_path)
                    if resolved:
                        imports.append(resolved)

            for match in config["use_namespace"].finditer(source):
                ns_path = match.group(1).replace("\\", "/")
                candidate = self._project_root / (ns_path + ".php")
                resolved = self._to_relative(candidate)
                if resolved:
                    imports.append(resolved)

        elif lang in ("c", "cpp", "objective_c"):
            for pattern_key in config:
                if pattern_key == "extensions":
                    continue
                for match in config[pattern_key].finditer(source):
                    included = match.group(1)
                    resolved = self._resolve_c_include(included, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang in ("csharp", "kotlin", "scala", "groovy"):
            for match in config["import_single"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_dot_import(module, f".{lang}", source_path)
                if resolved:
                    imports.append(resolved)

        elif lang == "ruby":
            for pattern_key in ("require", "require_relative", "load"):
                if pattern_key not in config:
                    continue
                for match in config[pattern_key].finditer(source):
                    included = match.group(1)
                    resolved = self._resolve_ruby_require(included, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "lua":
            for pattern_key in ("require", "dofile"):
                if pattern_key not in config:
                    continue
                for match in config[pattern_key].finditer(source):
                    included = match.group(1)
                    resolved = self._resolve_lua_require(included, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "shell":
            for match in config["source"].finditer(source):
                included = match.group(1)
                resolved = self._resolve_shell_source(included, source_path)
                if resolved:
                    imports.append(resolved)

        elif lang == "dart":
            for pattern_key in ("import_single", "import_part", "part_of"):
                if pattern_key not in config:
                    continue
                for match in config[pattern_key].finditer(source):
                    included = match.group(1)
                    if included.startswith("dart:"):
                        continue
                    resolved = self._resolve_dart_import(included, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "perl":
            for pattern_key in ("use", "require"):
                for match in config[pattern_key].finditer(source):
                    module = match.group(1)
                    resolved = self._resolve_dot_import(module, ".pm", source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "elixir":
            for pattern_key in ("import", "require"):
                for match in config[pattern_key].finditer(source):
                    module = match.group(1)
                    resolved = self._resolve_elixir_import(module, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "haskell":
            for match in config["import"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_haskell_import(module, source_path)
                if resolved:
                    imports.append(resolved)

        elif lang == "zig":
            for match in config["import"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_zig_import(module, source_path)
                if resolved:
                    imports.append(resolved)

        elif lang == "rlang":
            for match in config["source"].finditer(source):
                included = match.group(1)
                resolved = self._resolve_r_source(included, source_path)
                if resolved:
                    imports.append(resolved)

        elif lang == "nim":
            for pattern_key in ("import", "include"):
                for match in config[pattern_key].finditer(source):
                    module = match.group(1)
                    resolved = self._resolve_nim_import(module, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang in ("clojure",):
            for pattern_key in ("require", "ns_require"):
                if pattern_key not in config:
                    continue
                for match in config[pattern_key].finditer(source):
                    resolved = self._resolve_clojure_require(match.group(0), source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "erlang":
            for pattern_key in ("include", "include_lib"):
                for match in config[pattern_key].finditer(source):
                    included = match.group(1)
                    resolved = self._resolve_erlang_include(included, source_path)
                    if resolved:
                        imports.append(resolved)

        elif lang == "solidity":
            for pattern_key in ("import", "import_from"):
                for match in config[pattern_key].finditer(source):
                    included = match.group(1)
                    if included.startswith("http") or included.startswith("//"):
                        continue
                    resolved = self._resolve_c_include(included, source_path)
                    if resolved:
                        imports.append(resolved)

        return sorted(set(imports))

    def _resolve_go_import(self, module: str, source_path: Path) -> Optional[str]:
        parts = module.split("/")
        candidates = [
            self._project_root / "/".join(parts),
            self._project_root / f"{'/'.join(parts)}.go",
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_rust_import(self, module: str, source_path: Path) -> Optional[str]:
        if module.startswith("crate::"):
            relative = module[6:].replace("::", "/")
        elif module.startswith("self::"):
            relative = module[5:].replace("::", "/")
        elif module.startswith("super::"):
            parts = module.split("::")
            depth = sum(1 for p in parts if p == "super")
            remaining = "/".join(parts[depth:]) if len(parts) > depth else ""
            current = source_path.parent
            for _ in range(depth):
                current = current.parent
            relative = str(current.relative_to(self._project_root)).replace(os.sep, "/")
            if remaining:
                relative += "/" + remaining
        else:
            return None

        candidates = [self._project_root / (relative + ".rs"), self._project_root / relative / "mod.rs"]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_java_import(self, module: str, source_path: Path) -> Optional[str]:
        if module.startswith("static "):
            module = module[7:]
        parts = module.split(".")
        for depth in range(len(parts), 0, -1):
            candidate = self._project_root / f"{'/'.join(parts[:depth])}.java"
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_php_include(self, included: str, source_path: Path) -> Optional[str]:
        included = included.replace("\\", "/")
        if included.startswith("/") or included.startswith("http"):
            return None

        candidates = [
            source_path.parent / included,
            source_path.parent / (included + ".php"),
            self._project_root / included,
            self._project_root / (included + ".php"),
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_php_use(self, namespace: str, source_path: Path) -> Optional[str]:
        # 解析 PHP use 语句中的命名空间引用到文件路径
        # use App\Models\User -> App/Models/User.php 或 src/App/Models/User.php
        namespace = namespace.replace("\\", "/").lstrip("\\")
        candidates = [
            self._project_root / f"{namespace}.php",
            source_path.parent / f"{namespace}.php",
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved

        # 尝试从根目录向上搜索
        current = source_path.parent
        while current > self._project_root:
            candidate = current / f"{namespace}.php"
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
            if current == self._project_root:
                break
            current = current.parent

        return None

    def _resolve_c_include(self, included: str, source_path: Path) -> Optional[str]:
        if included.startswith("/") or included.startswith("http"):
            return None
        search_dirs = [source_path.parent, self._project_root]
        for search_dir in search_dirs:
            candidate = search_dir / included
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        # Walk up from source to project root
        current = source_path.parent
        while current > self._project_root:
            current = current.parent
            candidate = current / included
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
            if current == self._project_root:
                break
        return None

    def _resolve_dot_import(self, module: str, ext: str, source_path: Path) -> Optional[str]:
        parts = module.split(".")
        search_dirs = [source_path.parent, self._project_root]
        for search_dir in search_dirs:
            for depth in range(len(parts), 0, -1):
                candidate = search_dir / f"{'/'.join(parts[:depth])}{ext}"
                resolved = self._to_relative(candidate)
                if resolved:
                    return resolved
        return None

    def _resolve_ruby_require(self, included: str, source_path: Path) -> Optional[str]:
        candidates = [
            source_path.parent / (included + ".rb"),
            self._project_root / (included + ".rb"),
            source_path.parent / included,
            self._project_root / included,
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_lua_require(self, included: str, source_path: Path) -> Optional[str]:
        included = included.replace(".", "/")
        candidates = [
            source_path.parent / (included + ".lua"),
            self._project_root / (included + ".lua"),
            source_path.parent / (included + "/init.lua"),
            self._project_root / (included + "/init.lua"),
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_shell_source(self, included: str, source_path: Path) -> Optional[str]:
        candidates = [
            source_path.parent / included,
            self._project_root / included,
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_dart_import(self, included: str, source_path: Path) -> Optional[str]:
        if included.startswith("package:"):
            included = included[8:]
        if included.startswith("dart:"):
            return None
        candidates = [
            self._project_root / (included + ".dart"),
            source_path.parent / (included + ".dart"),
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_elixir_import(self, module: str, source_path: Path) -> Optional[str]:
        parts = module.split(".")
        for depth in range(len(parts), 0, -1):
            name = "_".join(p.lower() for p in parts[:depth])
            for ext in (".ex", ".exs"):
                candidate = self._project_root / f"{'/'.join(parts[:depth - 1])}/{name}{ext}" if depth > 1 else self._project_root / f"{name}{ext}"
                resolved = self._to_relative(candidate)
                if resolved:
                    return resolved
        return None

    def _resolve_haskell_import(self, module: str, source_path: Path) -> Optional[str]:
        parts = module.split(".")
        candidates = [
            self._project_root / f"{'/'.join(parts)}.hs",
            self._project_root / f"{'/'.join(parts[0].upper() + parts[1:])}.hs",
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_zig_import(self, module: str, source_path: Path) -> Optional[str]:
        candidates = [
            source_path.parent / (module + ".zig"),
            self._project_root / (module + ".zig"),
            source_path.parent / (module + "/" + "module.zig"),
            self._project_root / (module + "/" + "module.zig"),
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_r_source(self, included: str, source_path: Path) -> Optional[str]:
        candidates = [
            source_path.parent / included,
            self._project_root / included,
            source_path.parent / (included + ".R"),
            self._project_root / (included + ".R"),
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_nim_import(self, module: str, source_path: Path) -> Optional[str]:
        module = module.replace("/", os.sep)
        candidates = [
            self._project_root / (module + ".nim"),
            self._project_root / module,
            source_path.parent / (module + ".nim"),
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_clojure_require(self, match_text: str, source_path: Path) -> Optional[str]:
        parts = re.findall(r'[\w.\-]+', match_text)
        for part in parts:
            part_clean = part.replace("-", "_").replace(".", "/")
            for ext in (".clj", ".cljs", ".cljc"):
                candidate = self._project_root / (part_clean + ext)
                resolved = self._to_relative(candidate)
                if resolved:
                    return resolved
            candidate = self._project_root / part_clean
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_erlang_include(self, included: str, source_path: Path) -> Optional[str]:
        candidates = [
            source_path.parent / included,
            self._project_root / included,
            self._project_root / "include" / included,
            self._project_root / "src" / included,
        ]
        for candidate in candidates:
            resolved = self._to_relative(candidate)
            if resolved:
                return resolved
        return None

    def _to_relative(self, candidate: Path) -> Optional[str]:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return str(resolved.relative_to(self._project_root)).replace(os.sep, "/")
        except (ValueError, OSError):
            pass
        return None

    def _extract_cross_refs(self, source: str, lang: str, config: dict, source_path: Path) -> dict[str, list[str]]:
        """提取跨文件符号引用：追踪非 Python/JS 语言的符号使用。"""
        cross_refs: dict[str, list[str]] = {}
        source_dir = source_path.parent

        # symbol_name -> resolved_relative_path
        symbol_to_module: dict[str, str] = {}

        # Java / Kotlin / Scala / Dart / Groovy / C# - import 语句
        if lang in ("java", "kotlin", "scala", "groovy", "csharp"):
            import_pattern = config.get("import_single")
            if import_pattern:
                for match in import_pattern.finditer(source):
                    full_name = match.group(1)
                    # 提取类名 (最后一个 . 之后的部分)
                    class_name = full_name.split(".")[-1]
                    resolved = self._resolve_dot_import(full_name, f".{lang}", source_path)
                    if resolved:
                        symbol_to_module[class_name] = resolved

        # Go - import 语句
        if lang == "go":
            for match in config["single_import"].finditer(source):
                module = match.group(1)
                resolved = self._resolve_go_import(module, source_path)
                if resolved:
                    pkg_name = module.split("/")[-1]
                    symbol_to_module[pkg_name] = resolved
            for match in config["multi_import"].finditer(source):
                block = match.group(1)
                for inner in config["inner_import"].finditer(block):
                    module = inner.group(1)
                    resolved = self._resolve_go_import(module, source_path)
                    if resolved:
                        pkg_name = module.split("/")[-1]
                        symbol_to_module[pkg_name] = resolved

        # PHP - use 语句
        if lang == "php":
            use_pattern = config.get("use_namespace")
            if use_pattern:
                for match in use_pattern.finditer(source):
                    full_name = match.group(1)
                    class_name = full_name.split("\\")[-1]
                    resolved = self._resolve_php_use(full_name, source_path)
                    if resolved:
                        symbol_to_module[class_name] = resolved

        if not symbol_to_module:
            return cross_refs

        # Step 2: 检查符号是否在代码中被使用
        for symbol, resolved_path in symbol_to_module.items():
            usage_pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
            # 排除 import/use 语句行
            lines = source.split("\n")
            found = False
            for line in lines:
                if not re.match(r'^\s*(?:import|using|require|include|use)\s', line):
                    if usage_pattern.search(line):
                        found = True
                        break
            if found:
                if resolved_path not in cross_refs:
                    cross_refs[resolved_path] = []
                if symbol not in cross_refs[resolved_path]:
                    cross_refs[resolved_path].append(symbol)

        return cross_refs

    def _extract_exports(self, source: str, lang: str) -> list[str]:
        exports: list[str] = []
        patterns = LANG_EXPORT_PATTERNS.get(lang, [])
        for pattern, kind in patterns:
            for match in pattern.finditer(source):
                name = match.group(1)
                if not name.startswith("_"):
                    exports.append(f"{kind}:{name}")
        return exports

    def _extract_purpose(self, source: str, lang: str) -> str:
        patterns = LANG_EXPORT_PATTERNS.get(lang, [])

        classes = []
        functions = []
        for pattern, kind in patterns:
            for match in pattern.finditer(source):
                name = match.group(1)
                if name.startswith("_"):
                    continue
                if kind in ("class", "mod"):
                    if name not in classes:
                        classes.append(name)
                elif kind == "fn":
                    if name not in functions:
                        functions.append(name)

        if classes:
            names = ", ".join(classes[:3])
            suffix = " ..." if len(classes) > 3 else ""
            return f"定义类型: {names}{suffix}"
        if functions:
            names = ", ".join(functions[:3])
            suffix = " ..." if len(functions) > 3 else ""
            return f"定义函数: {names}{suffix}"
        return "无公开导出"