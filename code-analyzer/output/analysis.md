# 项目代码分析报告

> 自动生成于分析工具

---

## 项目概览

| 指标 | 数值 |
|------|------|
| 总文件数 | 22 |
| 总代码行 | 2443 |
| 总依赖关系 | 21 |

### 架构分层

| 层级 | 文件数 |
|------|--------|
| application | 1 |
| common | 10 |
| domain | 1 |
| foundation | 10 |

## 依赖关系图

```mermaid
graph TD
    N0["run.py"]
    N1["run_gui.py"]
    N2["src/<br/>gui_app.py"]
    N3["src/<br/>main.py"]
    N4["src/<br/>__init__.py"]
    N5["src/<br/>analyzer/<br/>incremental_cache.py"]
    N6["src/<br/>analyzer/<br/>llm_client.py"]
    N7["src/<br/>analyzer/<br/>rule_engine.py"]
    N8["src/<br/>analyzer/<br/>__init__.py"]
    N9["src/<br/>graph/<br/>dependency_graph.py"]
    N10["src/<br/>graph/<br/>__init__.py"]
    N11["src/<br/>parser/<br/>generic_parser.py"]
    N12["src/<br/>parser/<br/>js_parser.py"]
    N13["src/<br/>parser/<br/>python_parser.py"]
    N14["src/<br/>parser/<br/>__init__.py"]
    N15["src/<br/>reporter/<br/>html_reporter.py"]
    N16["src/<br/>reporter/<br/>json_reporter.py"]
    N17["src/<br/>reporter/<br/>markdown_reporter.py"]
    N18["src/<br/>reporter/<br/>__init__.py"]
    N19["tests/<br/>fixtures/<br/>go/<br/>server.go"]
    N20["tests/<br/>fixtures/<br/>java/<br/>Application.java"]
    N21["tests/<br/>fixtures/<br/>rust/<br/>app.rs"]

    N0 --> N3
    N1 --> N2
    N3 --> N5
    N3 --> N6
    N3 --> N7
    N3 --> N9
    N3 --> N11
    N3 --> N12
    N3 --> N13
    N3 --> N15
    N3 --> N16
    N3 --> N17
    N5 --> N9
    N6 --> N9
    N7 --> N9
    N11 --> N9
    N12 --> N9
    N13 --> N9
    N15 --> N9
    N16 --> N9
    N17 --> N9
```

## 文件详情

### `run.py`

- **语言**: python
- **代码行数**: 11
- **架构层级**: 应用层
- **功能描述**: 模块文件
- **分析来源**: static

- **依赖文件**: [`src/main.py`](#srcmainpy)

---

### `run_gui.py`

- **语言**: python
- **代码行数**: 11
- **架构层级**: 公共层
- **功能描述**: 模块文件
- **分析来源**: static

- **依赖文件**: [`src/gui_app.py`](#srcguiapppy)

---

### `src/__init__.py`

- **语言**: python
- **代码行数**: 0
- **架构层级**: 基础层
- **功能描述**: (暂无)
- **分析来源**: static

---

### `src/analyzer/__init__.py`

- **语言**: python
- **代码行数**: 0
- **架构层级**: 基础层
- **功能描述**: (暂无)
- **分析来源**: static

---

### `src/analyzer/incremental_cache.py`

- **语言**: python
- **代码行数**: 84
- **架构层级**: 公共层
- **功能描述**: 定义类: IncrementalCache
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/analyzer/llm_client.py`

- **语言**: python
- **代码行数**: 106
- **架构层级**: 公共层
- **功能描述**: 定义类: LLMAnalyzer
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/analyzer/rule_engine.py`

- **语言**: python
- **代码行数**: 219
- **架构层级**: 公共层
- **功能描述**: 定义类: RuleViolation, RuleResult, RuleEngine
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/graph/__init__.py`

- **语言**: python
- **代码行数**: 0
- **架构层级**: 基础层
- **功能描述**: (暂无)
- **分析来源**: static

---

### `src/graph/dependency_graph.py`

- **语言**: python
- **代码行数**: 162
- **架构层级**: 基础层
- **功能描述**: 定义类: FileNode, DependencyGraph
- **分析来源**: static

- **被引用者**: `src/main.py`, `src/analyzer/incremental_cache.py`, `src/analyzer/llm_client.py`, `src/analyzer/rule_engine.py`, `src/parser/generic_parser.py`, `src/parser/js_parser.py`, `src/parser/python_parser.py`, `src/reporter/html_reporter.py` ...（共 10 个）

---

### `src/gui_app.py`

- **语言**: python
- **代码行数**: 281
- **架构层级**: 基础层
- **功能描述**: 定义类: RedirectText, AnalyzerGUI
- **分析来源**: static

- **对外导出**: `class:RedirectText`, `class:AnalyzerGUI`, `fn:main`

- **被引用者**: `run_gui.py`

---

### `src/main.py`

- **语言**: python
- **代码行数**: 331
- **架构层级**: 领域层
- **功能描述**: 定义函数: load_config, scan_files, detect_language ...
- **分析来源**: static

- **对外导出**: `var:SUPPORTED_EXTENSIONS`, `fn:load_config`, `fn:scan_files`, `fn:detect_language`, `fn:run_analysis`, `fn:generate_reports`, `fn:print_summary`, `fn:print_rule_result`, `fn:main`

- **依赖文件**: [`src/analyzer/incremental_cache.py`](#srcanalyzerincrementalcachepy), [`src/analyzer/llm_client.py`](#srcanalyzerllmclientpy), [`src/analyzer/rule_engine.py`](#srcanalyzerruleenginepy), [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy), [`src/parser/generic_parser.py`](#srcparsergenericparserpy), [`src/parser/js_parser.py`](#srcparserjsparserpy), [`src/parser/python_parser.py`](#srcparserpythonparserpy), [`src/reporter/html_reporter.py`](#srcreporterhtmlreporterpy) ...（共 10 个）

- **被引用者**: `run.py`

---

### `src/parser/__init__.py`

- **语言**: python
- **代码行数**: 0
- **架构层级**: 基础层
- **功能描述**: (暂无)
- **分析来源**: static

---

### `src/parser/generic_parser.py`

- **语言**: python
- **代码行数**: 228
- **架构层级**: 公共层
- **功能描述**: 定义类: GenericParser
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/parser/js_parser.py`

- **语言**: python
- **代码行数**: 171
- **架构层级**: 公共层
- **功能描述**: 定义类: JSParser
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/parser/python_parser.py`

- **语言**: python
- **代码行数**: 158
- **架构层级**: 公共层
- **功能描述**: 定义类: PythonParser
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/reporter/__init__.py`

- **语言**: python
- **代码行数**: 0
- **架构层级**: 基础层
- **功能描述**: (暂无)
- **分析来源**: static

---

### `src/reporter/html_reporter.py`

- **语言**: python
- **代码行数**: 394
- **架构层级**: 公共层
- **功能描述**: 定义类: HTMLReporter
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/reporter/json_reporter.py`

- **语言**: python
- **代码行数**: 32
- **架构层级**: 公共层
- **功能描述**: 定义类: JSONReporter
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `src/reporter/markdown_reporter.py`

- **语言**: python
- **代码行数**: 138
- **架构层级**: 公共层
- **功能描述**: 定义类: MarkdownReporter
- **分析来源**: static

- **依赖文件**: [`src/graph/dependency_graph.py`](#srcgraphdependencygraphpy)

- **被引用者**: `src/main.py`

---

### `tests/fixtures/go/server.go`

- **语言**: go
- **代码行数**: 35
- **架构层级**: 基础层
- **功能描述**: 定义类型: Server, Config
- **分析来源**: static

---

### `tests/fixtures/java/Application.java`

- **语言**: java
- **代码行数**: 43
- **架构层级**: 基础层
- **功能描述**: 定义类型: Application
- **分析来源**: static

---

### `tests/fixtures/rust/app.rs`

- **语言**: rust
- **代码行数**: 39
- **架构层级**: 基础层
- **功能描述**: 定义类型: App, AppMode, Runnable ...
- **分析来源**: static

---
