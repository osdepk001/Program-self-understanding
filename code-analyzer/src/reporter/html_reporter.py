from __future__ import annotations

import json
from pathlib import Path

from ..graph.dependency_graph import DependencyGraph


class HTMLReporter:
    """生成包含交互式 D3.js 力导向依赖图的独立 HTML 文件。"""

    def generate(self, graph: DependencyGraph, output_dir: str) -> str:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        nodes_data = self._build_nodes_data(graph)
        links_data = self._build_links_data(graph)
        cycles_data = graph.get_cycles()
        stats = graph.get_stats()
        project_info = graph.project_info
        api_data = graph.api_endpoints
        db_data = graph.db_models
        quality_data = graph.quality
        git_data = graph.git_info
        security_data = graph.security

        graph_json = json.dumps(
            {"nodes": nodes_data, "links": links_data, "cycles": cycles_data},
            ensure_ascii=False,
        )
        stats_json = json.dumps(stats, ensure_ascii=False)
        project_json = json.dumps(project_info, ensure_ascii=False) if project_info else "{}"
        api_json = json.dumps(api_data, ensure_ascii=False) if api_data else "{}"
        db_json = json.dumps(db_data, ensure_ascii=False) if db_data else "{}"
        quality_json = json.dumps(quality_data, ensure_ascii=False) if quality_data else "{}"
        git_json = json.dumps(git_data, ensure_ascii=False) if git_data else "{}"
        security_json = json.dumps(security_data, ensure_ascii=False) if security_data else "{}"

        html = self._render_html(graph_json, stats_json, project_json, api_json, db_json, quality_json, git_json, security_json)

        output_file = out_path / "analysis.html"
        output_file.write_text(html, encoding="utf-8")
        return str(output_file)

    def _build_nodes_data(self, graph: DependencyGraph) -> list[dict]:
        nodes = graph.get_all_nodes()
        layer_colors = {
            "foundation": "#6c757d",
            "common": "#0d6efd",
            "domain": "#198754",
            "application": "#fd7e14",
            "interface": "#dc3545",
        }

        result = []
        for node in nodes:
            result.append({
                "id": node.relative_path,
                "label": node.relative_path.split("/")[-1],
                "fullPath": node.relative_path,
                "purpose": node.purpose or "(暂无描述)",
                "layer": node.layer or "unknown",
                "lines": node.lines,
                "language": node.language,
                "imports": node.imports,
                "importsCount": len(node.imports),
                "importedBy": node.imported_by,
                "importedByCount": len(node.imported_by),
                "crossRefs": node.cross_refs,
                "crossRefsCount": sum(len(v) for v in node.cross_refs.values()),
                "color": layer_colors.get(node.layer, "#adb5bd"),
                "callTargets": node.call_targets,
                "callTargetsCount": len(node.call_targets),
                "unusedImports": node.unused_imports,
                "unusedImportsCount": len(node.unused_imports),
            })
        return result

    def _build_links_data(self, graph: DependencyGraph) -> list[dict]:
        links = []
        for node in graph.get_all_nodes():
            for imp in node.imports:
                links.append({
                    "source": node.relative_path,
                    "target": imp,
                })
        return links

    def _render_html(self, graph_json: str, stats_json: str, project_json: str,
                      api_json: str, db_json: str, quality_json: str,
                      git_json: str, security_json: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>项目代码依赖关系图</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; background: #11111b; }}
#container {{ display: flex; height: 100vh; }}
#sidebar {{ width: 360px; background: #1e1e2e; color: #cdd6f4; overflow-y: auto; padding: 20px; flex-shrink: 0; display: flex; flex-direction: column; gap: 16px; }}
#sidebar h2 {{ font-size: 18px; color: #f5f5f5; }}
#search-box {{ width: 100%; padding: 8px 12px; border: 1px solid #45475a; border-radius: 6px; background: #313244; color: #cdd6f4; font-size: 13px; outline: none; }}
#search-box:focus {{ border-color: #89b4fa; }}
#search-box::placeholder {{ color: #6c7086; }}
#stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.stat-card {{ background: #313244; border-radius: 8px; padding: 10px; text-align: center; }}
.stat-card .num {{ font-size: 22px; font-weight: bold; color: #89b4fa; }}
.stat-card .lbl {{ font-size: 11px; color: #a6adc8; margin-top: 2px; }}
.stat-card.warn .num {{ color: #f38ba8; }}
#legend {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 11px; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
#project-overview {{ background: linear-gradient(135deg, #313244 0%, #45475a 100%); border-radius: 10px; padding: 14px; font-size: 13px; line-height: 1.8; border: 1px solid #585b70; }}
#project-overview .proj-type {{ font-size: 16px; font-weight: bold; color: #89b4fa; }}
#project-overview .proj-desc {{ font-size: 12px; color: #a6adc8; margin-top: 4px; }}
#project-overview .proj-row {{ display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 8px; }}
#project-overview .proj-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #1e1e2e; color: #cdd6f4; }}
#project-overview .proj-tag.fw {{ background: #1e1e2e; color: #89b4fa; }}
#project-overview .proj-tag.db {{ background: #1e1e2e; color: #a6e3a1; }}
#project-overview .proj-tag.bt {{ background: #1e1e2e; color: #f9e2af; }}
#project-overview .proj-tag.ep {{ background: #1e1e2e; color: #f38ba8; }}
#project-overview .proj-arch {{ font-size: 12px; color: #cba6f7; margin-top: 6px; }}
.section-panel {{ background: #313244; border-radius: 8px; padding: 12px; font-size: 12px; line-height: 1.6; }}
.section-panel h4 {{ font-size: 13px; color: #f5f5f5; margin-bottom: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
.section-panel h4 .arrow {{ font-size: 10px; transition: transform 0.2s; }}
.section-panel h4.collapsed .arrow {{ transform: rotate(-90deg); }}
.section-panel .section-body {{ max-height: 300px; overflow-y: auto; }}
.section-panel .section-body.hidden {{ display: none; }}
.api-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
.api-table th {{ text-align: left; padding: 4px 6px; background: #1e1e2e; color: #a6adc8; font-weight: normal; }}
.api-table td {{ padding: 3px 6px; border-bottom: 1px solid #45475a; }}
.api-method {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-weight: bold; font-size: 10px; }}
.api-method.get {{ background: #19875433; color: #198754; }}
.api-method.post {{ background: #0d6efd33; color: #0d6efd; }}
.api-method.put {{ background: #fd7e1433; color: #fd7e14; }}
.api-method.delete {{ background: #dc354533; color: #dc3545; }}
.api-method.patch {{ background: #6f42c133; color: #6f42c1; }}
.db-model {{ background: #1e1e2e; border-radius: 6px; padding: 8px; margin-bottom: 6px; }}
.db-model .model-name {{ font-weight: bold; color: #89b4fa; font-size: 12px; }}
.db-model .model-table {{ font-size: 10px; color: #6c7086; }}
.db-model .model-field {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; background: #45475a; margin: 2px; }}
.db-model .model-field.pk {{ background: #f9e2af33; color: #f9e2af; }}
.db-model .model-field.rel {{ background: #cba6f733; color: #cba6f7; }}
.quality-grade {{ display: inline-block; font-size: 28px; font-weight: bold; padding: 8px 20px; border-radius: 8px; }}
.quality-grade.A {{ background: #19875433; color: #198754; }}
.quality-grade.B {{ background: #0d6efd33; color: #0d6efd; }}
.quality-grade.C {{ background: #fd7e1433; color: #fd7e14; }}
.quality-grade.D {{ background: #dc354533; color: #dc3545; }}
.quality-grade.E,.quality-grade.F {{ background: #dc354533; color: #dc3545; }}
.quality-metric {{ display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #45475a55; }}
.quality-metric .qm-label {{ color: #a6adc8; }}
.quality-metric .qm-value {{ color: #cdd6f4; font-weight: bold; }}
.sec-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin: 2px; }}
.sec-badge.critical {{ background: #dc354533; color: #dc3545; }}
.sec-badge.high {{ background: #fd7e1433; color: #fd7e14; }}
.sec-badge.medium {{ background: #f9e2af33; color: #f9e2af; }}
.sec-badge.low {{ background: #0d6efd33; color: #0d6efd; }}
.git-row {{ display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #45475a55; font-size: 11px; }}
.git-row .git-label {{ color: #a6adc8; }}
.git-row .git-value {{ color: #cdd6f4; }}
#sidebar h3 {{ font-size: 14px; color: #f5f5f5; margin-top: 12px; padding-bottom: 6px; border-bottom: 1px solid #45475a; }}
#btn-row {{ display: flex; gap: 6px; }}
#btn-row button {{ flex: 1; padding: 7px 0; border: 1px solid #45475a; border-radius: 6px; background: #313244; color: #cdd6f4; font-size: 12px; cursor: pointer; transition: background 0.15s; }}
#btn-row button:hover {{ background: #45475a; }}
#detail {{ padding: 12px; background: #313244; border-radius: 8px; font-size: 13px; line-height: 1.6; display: none; }}
#detail.active {{ display: block; }}
#detail h3 {{ font-size: 14px; margin-bottom: 8px; color: #f9e2af; word-break: break-all; }}
#detail .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin: 2px 4px 2px 0; }}
#detail .dep-list {{ max-height: 120px; overflow-y: auto; margin-top: 4px; font-size: 11px; color: #a6adc8; }}
#detail .dep-list span {{ display: block; padding: 1px 0; }}
#graph {{ flex: 1; cursor: grab; position: relative; }}
#graph:active {{ cursor: grabbing; }}
#graph svg {{ width: 100%; height: 100%; }}
.node circle {{ stroke-width: 2px; transition: r 0.2s; }}
.node text {{ font-size: 10px; fill: #cdd6f4; pointer-events: none; }}
.node.dimmed text {{ opacity: 0.15; }}
.node.dimmed circle {{ opacity: 0.15; }}
.link {{ stroke: #45475a; stroke-opacity: 0.6; }}
.link.dimmed {{ opacity: 0.05; }}
.link.cycle-link {{ stroke: #f38ba8; stroke-opacity: 0.9; stroke-width: 2.5; stroke-dasharray: 6 3; animation: dash 1s linear infinite; }}
@keyframes dash {{ to {{ stroke-dashoffset: -18; }} }}
.tooltip {{ position: absolute; padding: 8px 12px; background: rgba(30,30,46,0.95); color: #f5f5f5; border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.15s; max-width: 260px; z-index: 10; }}
#filter-count {{ font-size: 11px; color: #6c7086; margin-top: -8px; display: none; }}
#filter-count.visible {{ display: block; }}
</style>
</head>
<body>
<div id="container">
<div id="sidebar">
    <h2>项目依赖关系图</h2>
    <div id="project-overview" style="display:none;"></div>
    <input type="text" id="search-box" placeholder="搜索文件名或路径..." autocomplete="off">
    <span id="filter-count"></span>
    <div id="stats-grid"></div>
    <div id="legend">
        <div class="legend-item"><span class="legend-dot" style="background:#6c757d"></span>基础层</div>
        <div class="legend-item"><span class="legend-dot" style="background:#0d6efd"></span>公共层</div>
        <div class="legend-item"><span class="legend-dot" style="background:#198754"></span>领域层</div>
        <div class="legend-item"><span class="legend-dot" style="background:#fd7e14"></span>应用层</div>
        <div class="legend-item"><span class="legend-dot" style="background:#dc3545"></span>接口层</div>
        <div class="legend-item"><span class="legend-dot" style="background:#f38ba8;width:16px;border-radius:2px;height:2px"></span>循环依赖</div>
    </div>
    <div id="btn-row">
        <button id="btn-svg" title="导出 SVG 矢量图">导出 SVG</button>
        <button id="btn-png" title="导出 PNG 位图">导出 PNG</button>
        <button id="btn-reset" title="重置视图">重置视图</button>
    </div>
    <div class="detail" id="detail"></div>
    <div id="cycle-panel" style="display:none; padding:12px; background:#f38ba822; border-radius:8px; border:1px solid #f38ba844; margin-top:8px;">
        <h3 style="font-size:14px; color:#f38ba8; margin-bottom:8px;">循环依赖</h3>
        <div id="cycle-list" style="font-size:12px; line-height:1.8;"></div>
    </div>
    <div id="call-panel" style="display:none; padding:12px; background:#313244; border-radius:8px; margin-top:8px;">
        <h3 style="font-size:14px; color:#89b4fa; margin-bottom:8px;">调用管理</h3>
        <div id="call-list" style="font-size:12px; line-height:1.8; max-height:300px; overflow-y:auto;"></div>
    </div>
    <div id="api-panel" class="section-panel" style="display:none;">
        <h4 onclick="toggleSection(this)">API 端点 <span style="color:#a6adc8;font-size:11px;" id="api-count"></span> <span class="arrow">▼</span></h4>
        <div class="section-body" id="api-body"></div>
    </div>
    <div id="db-panel" class="section-panel" style="display:none;">
        <h4 onclick="toggleSection(this)">数据模型 <span style="color:#a6adc8;font-size:11px;" id="db-count"></span> <span class="arrow">▼</span></h4>
        <div class="section-body" id="db-body"></div>
    </div>
    <div id="quality-panel" class="section-panel" style="display:none;">
        <h4 onclick="toggleSection(this)">代码质量 <span class="arrow">▼</span></h4>
        <div class="section-body" id="quality-body"></div>
    </div>
    <div id="git-panel" class="section-panel" style="display:none;">
        <h4 onclick="toggleSection(this)">Git 历史 <span class="arrow">▼</span></h4>
        <div class="section-body" id="git-body"></div>
    </div>
    <div id="security-panel" class="section-panel" style="display:none;">
        <h4 onclick="toggleSection(this)">安全扫描 <span class="arrow">▼</span></h4>
        <div class="section-body" id="security-body"></div>
    </div>
</div>
<div id="graph"></div>
</div>
<div class="tooltip" id="tooltip"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = {graph_json};
const STATS = {stats_json};
const PROJECT = {project_json};
const API_DATA = {api_json};
const DB_DATA = {db_json};
const QUALITY = {quality_json};
const GIT_DATA = {git_json};
const SECURITY = {security_json};

(function() {{
    function renderProjectOverview() {{
        const el = document.getElementById("project-overview");
        if (!PROJECT || !PROJECT.project_type || PROJECT.project_type === "unknown") {{
            el.style.display = "none";
            return;
        }}
        el.style.display = "block";
        let html = '';
        html += '<div class="proj-type">' + (PROJECT.project_subtype || PROJECT.project_type) + '</div>';
        if (PROJECT.display_name) {{
            html += '<div class="proj-desc">' + PROJECT.display_name + '</div>';
        }}
        if (PROJECT.description) {{
            html += '<div class="proj-desc">' + PROJECT.description + '</div>';
        }}
        html += '<div class="proj-row">';
        if (PROJECT.frameworks && PROJECT.frameworks.length > 0) {{
            html += PROJECT.frameworks.map(f => '<span class="proj-tag fw">' + f + '</span>').join('');
        }}
        if (PROJECT.databases && PROJECT.databases.length > 0) {{
            html += PROJECT.databases.map(d => '<span class="proj-tag db">' + d + '</span>').join('');
        }}
        if (PROJECT.build_tools && PROJECT.build_tools.length > 0) {{
            html += PROJECT.build_tools.map(b => '<span class="proj-tag bt">' + b + '</span>').join('');
        }}
        html += '</div>';
        if (PROJECT.architecture) {{
            html += '<div class="proj-arch">架构: ' + PROJECT.architecture + '</div>';
        }}
        if (PROJECT.entry_points && PROJECT.entry_points.length > 0) {{
            html += '<div style="margin-top:6px;font-size:11px;color:#6c7086;">入口: ' + PROJECT.entry_points.slice(0, 5).join(', ') + '</div>';
        }}
        el.innerHTML = html;
    }}
    renderProjectOverview();

    // ========== API 端点渲染 ==========
    function renderApiPanel() {{
        const panel = document.getElementById("api-panel");
        const body = document.getElementById("api-body");
        const count = document.getElementById("api-count");
        if (!API_DATA || !API_DATA.endpoints || API_DATA.endpoints.length === 0) {{
            panel.style.display = "none"; return;
        }}
        panel.style.display = "block";
        count.textContent = '(' + API_DATA.total + ' 个端点)';
        let html = '<table class="api-table"><tr><th>方法</th><th>路径</th><th>处理器</th><th>文件</th></tr>';
        const endpoints = API_DATA.endpoints.slice(0, 50);
        endpoints.forEach(ep => {{
            const method = ep.method.toLowerCase();
            html += '<tr><td><span class="api-method ' + method + '">' + ep.method + '</span></td>';
            html += '<td style="color:#cdd6f4;font-family:monospace;">' + ep.path + '</td>';
            html += '<td style="color:#a6adc8;">' + (ep.handler || '-') + '</td>';
            html += '<td style="color:#6c7086;font-size:10px;">' + (ep.file_path || '') + '</td></tr>';
        }});
        if (API_DATA.endpoints.length > 50) {{
            html += '<tr><td colspan="4" style="text-align:center;color:#6c7086;padding:8px;">... 还有 ' + (API_DATA.endpoints.length - 50) + ' 个端点</td></tr>';
        }}
        html += '</table>';
        body.innerHTML = html;
    }}
    renderApiPanel();

    // ========== 数据模型渲染 ==========
    function renderDbPanel() {{
        const panel = document.getElementById("db-panel");
        const body = document.getElementById("db-body");
        const count = document.getElementById("db-count");
        if (!DB_DATA || !DB_DATA.models || DB_DATA.models.length === 0) {{
            panel.style.display = "none"; return;
        }}
        panel.style.display = "block";
        count.textContent = '(' + DB_DATA.total_tables + ' 个表, ' + DB_DATA.total_fields + ' 个字段)';
        let html = '';
        DB_DATA.models.forEach(m => {{
            html += '<div class="db-model">';
            html += '<div class="model-name">' + m.class_name + '</div>';
            html += '<div class="model-table">' + (m.orm || '') + ': ' + m.table_name + ' (' + (m.file_path || '') + ')</div>';
            html += '<div style="margin-top:4px;">';
            m.fields.forEach(f => {{
                let cls = 'model-field';
                if (f.primary_key) cls += ' pk';
                if (f.is_relation) cls += ' rel';
                html += '<span class="' + cls + '">' + f.name + (f.type ? ': ' + f.type : '') + '</span>';
            }});
            html += '</div></div>';
        }});
        body.innerHTML = html;
    }}
    renderDbPanel();

    // ========== 代码质量渲染 ==========
    function renderQualityPanel() {{
        const panel = document.getElementById("quality-panel");
        const body = document.getElementById("quality-body");
        if (!QUALITY || !QUALITY.grade) {{
            panel.style.display = "none"; return;
        }}
        panel.style.display = "block";
        let html = '<div style="text-align:center;margin-bottom:8px;"><span class="quality-grade ' + QUALITY.grade + '">' + QUALITY.grade + '</span></div>';
        html += '<div class="quality-metric"><span class="qm-label">总代码行</span><span class="qm-value">' + (QUALITY.total_lines || 0) + '</span></div>';
        html += '<div class="quality-metric"><span class="qm-label">有效代码行</span><span class="qm-value">' + (QUALITY.code_lines || 0) + '</span></div>';
        html += '<div class="quality-metric"><span class="qm-label">注释率</span><span class="qm-value">' + ((QUALITY.comment_ratio || 0) * 100).toFixed(1) + '%</span></div>';
        html += '<div class="quality-metric"><span class="qm-label">函数/方法数</span><span class="qm-value">' + (QUALITY.function_count || 0) + '</span></div>';
        html += '<div class="quality-metric"><span class="qm-label">平均圈复杂度</span><span class="qm-value">' + (QUALITY.avg_complexity || 0) + '</span></div>';
        if (QUALITY.complex_functions && QUALITY.complex_functions.length > 0) {{
            html += '<div style="margin-top:8px;color:#f38ba8;font-size:11px;">高复杂度函数:</div>';
            QUALITY.complex_functions.slice(0, 5).forEach(f => {{
                html += '<div style="font-size:11px;color:#a6adc8;padding:2px 0;">' + f.name + ' (复杂度:' + f.complexity + ') <span style="color:#6c7086;">' + (f.file || '') + ':' + f.line + '</span></div>';
            }});
        }}
        body.innerHTML = html;
    }}
    renderQualityPanel();

    // ========== Git 历史渲染 ==========
    function renderGitPanel() {{
        const panel = document.getElementById("git-panel");
        const body = document.getElementById("git-body");
        if (!GIT_DATA || !GIT_DATA.is_git_repo) {{
            panel.style.display = "none"; return;
        }}
        panel.style.display = "block";
        let html = '';
        html += '<div class="git-row"><span class="git-label">分支</span><span class="git-value">' + (GIT_DATA.current_branch || '-') + '</span></div>';
        html += '<div class="git-row"><span class="git-label">总提交</span><span class="git-value">' + (GIT_DATA.total_commits || 0) + '</span></div>';
        html += '<div class="git-row"><span class="git-label">贡献者</span><span class="git-value">' + (GIT_DATA.contributor_count || 0) + '</span></div>';
        if (GIT_DATA.contributors && GIT_DATA.contributors.length > 0) {{
            html += '<div style="margin-top:8px;color:#a6adc8;font-size:11px;">贡献者 TOP5:</div>';
            GIT_DATA.contributors.slice(0, 5).forEach(c => {{
                html += '<div class="git-row"><span class="git-label">' + c.name + '</span><span class="git-value">' + c.commits + ' 次</span></div>';
            }});
        }}
        if (GIT_DATA.top_changed_files && GIT_DATA.top_changed_files.length > 0) {{
            html += '<div style="margin-top:8px;color:#a6adc8;font-size:11px;">高频修改文件:</div>';
            GIT_DATA.top_changed_files.slice(0, 5).forEach(f => {{
                html += '<div style="font-size:10px;color:#6c7086;padding:1px 0;">' + f.file + ' (' + f.changes + '次)</div>';
            }});
        }}
        if (GIT_DATA.recent_commits && GIT_DATA.recent_commits.length > 0) {{
            html += '<div style="margin-top:8px;color:#a6adc8;font-size:11px;">最近提交:</div>';
            GIT_DATA.recent_commits.slice(0, 5).forEach(c => {{
                html += '<div style="font-size:10px;color:#6c7086;padding:1px 0;">' + c.hash + ' ' + c.date + ' <span style="color:#7f849c;">' + c.message + '</span></div>';
            }});
        }}
        body.innerHTML = html;
    }}
    renderGitPanel();

    // ========== 安全扫描渲染 ==========
    function renderSecurityPanel() {{
        const panel = document.getElementById("security-panel");
        const body = document.getElementById("security-body");
        if (!SECURITY || !SECURITY.total_issues || SECURITY.total_issues === 0) {{
            panel.style.display = "none"; return;
        }}
        panel.style.display = "block";
        let html = '<div style="text-align:center;margin-bottom:8px;">';
        if (SECURITY.critical) html += '<span class="sec-badge critical">严重 ' + SECURITY.critical + '</span>';
        if (SECURITY.high) html += '<span class="sec-badge high">高危 ' + SECURITY.high + '</span>';
        if (SECURITY.medium) html += '<span class="sec-badge medium">中危 ' + SECURITY.medium + '</span>';
        if (SECURITY.low) html += '<span class="sec-badge low">低危 ' + SECURITY.low + '</span>';
        html += '</div>';
        if (SECURITY.issues && SECURITY.issues.length > 0) {{
            SECURITY.issues.slice(0, 10).forEach(issue => {{
                html += '<div style="font-size:11px;padding:4px 0;border-bottom:1px solid #45475a55;">';
                html += '<span class="sec-badge ' + issue.severity + '">' + issue.severity + '</span> ';
                html += '<span style="color:#cdd6f4;">' + issue.title + '</span>';
                html += '<div style="color:#6c7086;font-size:10px;">' + (issue.file || '') + ':' + (issue.line || '') + '</div>';
                if (issue.snippet) {{
                    html += '<div style="color:#7f849c;font-size:10px;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + issue.snippet + '</div>';
                }}
                html += '</div>';
            }});
        }}
        body.innerHTML = html;
    }}
    renderSecurityPanel();

    // ========== 折叠面板 ==========
    function toggleSection(h4) {{
        const body = h4.nextElementSibling;
        if (body.classList.contains('hidden')) {{
            body.classList.remove('hidden');
            h4.classList.remove('collapsed');
        }} else {{
            body.classList.add('hidden');
            h4.classList.add('collapsed');
        }}
    }}

    function renderStats() {{
        const grid = document.getElementById("stats-grid");
        const cycleClass = STATS.cycles > 0 ? ' warn' : '';
        grid.innerHTML = `
            <div class="stat-card"><div class="num">${{STATS.total_files}}</div><div class="lbl">总文件数</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_lines}}</div><div class="lbl">总代码行</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_imports}}</div><div class="lbl">依赖关系</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_xrefs}}</div><div class="lbl">符号引用</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_calls}}</div><div class="lbl">调用关系</div></div>
            <div class="stat-card warn"><div class="num">${{STATS.total_unused}}</div><div class="lbl">未使用导入</div></div>
            <div class="stat-card${{cycleClass}}"><div class="num">${{STATS.cycles}}</div><div class="lbl">循环依赖</div></div>
        `;
    }}
    renderStats();

    const cycleEdges = new Set();
    if (DATA.cycles) {{
        DATA.cycles.forEach(cycle => {{
            for (let i = 0; i < cycle.length - 1; i++) {{
                cycleEdges.add(cycle[i] + "|||" + cycle[i + 1]);
                cycleEdges.add(cycle[i + 1] + "|||" + cycle[i]);
            }}
        }});
    }}

    // 渲染循环依赖面板
    function renderCyclePanel() {{
        const panel = document.getElementById("cycle-panel");
        const list = document.getElementById("cycle-list");
        if (!DATA.cycles || DATA.cycles.length === 0) {{
            panel.style.display = "none";
            return;
        }}
        panel.style.display = "block";
        let html = "";
        DATA.cycles.forEach((cycle, i) => {{
            const chain = cycle.map(c => `<span style="color:#f38ba8;cursor:pointer" onclick="highlightCycleNode('${{c}}')">${{c.split("/").pop()}}</span>`).join(' <span style="color:#a6adc8">&#8594;</span> ');
            html += '<div style="margin-bottom:6px;padding:6px;background:#f38ba815;border-radius:4px;"><span style="color:#6c7086">#' + (i+1) + '</span> ' + chain + '</div>';
        }});
        list.innerHTML = html;
    }}
    renderCyclePanel();

    // 渲染调用管理面板
    function renderCallPanel() {{
        const panel = document.getElementById("call-panel");
        const list = document.getElementById("call-list");
        const allCalls = DATA.nodes.flatMap(n => (n.callTargets || []).map(t => ({{ from: n.id, ...t }})));
        if (allCalls.length === 0) {{
            panel.style.display = "none";
            return;
        }}
        panel.style.display = "block";
        const byFile = {{}};
        allCalls.forEach(c => {{
            const key = c.file;
            if (!byFile[key]) byFile[key] = [];
            byFile[key].push(c);
        }});
        let html = "";
        for (const [file, calls] of Object.entries(byFile)) {{
            const fileName = file.split("/").pop();
            html += '<div style="margin-bottom:6px;padding:6px;background:#89b4fa11;border-radius:4px;">';
            html += '<span style="color:#89b4fa;cursor:pointer" onclick="highlightCycleNode(`${{file}}`)">' + fileName + '</span>';
            html += '<span style="color:#6c7086"> (被 ' + calls.length + ' 次调用)</span>';
            html += '<div style="margin-top:2px;padding-left:8px;">';
            const uniqueCallers = [...new Set(calls.map(c => c.from))].slice(0, 5);
            uniqueCallers.forEach(caller => {{
                html += '<span style="color:#a6adc8">&#8627; ' + caller.split("/").pop() + '</span><br/>';
            }});
            if (calls.length > uniqueCallers.length) {{
                html += '<span style="color:#6c7086">... 还有 ' + (calls.length - uniqueCallers.length) + ' 个调用者</span><br/>';
            }}
            html += '</div></div>';
        }}
        list.innerHTML = html;
    }}
    renderCallPanel();

    window.highlightCycleNode = function(path) {{
        const searchBox = document.getElementById("search-box");
        searchBox.value = path;
        searchBox.dispatchEvent(new Event("input"));
        showDetail(DATA.nodes.find(n => n.id === path));
    }};

    const width = document.getElementById("graph").clientWidth;
    const height = window.innerHeight;

    const svg = d3.select("#graph")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    const defs = svg.append("defs");
    const filter = defs.append("filter").attr("id", "shadow");
    filter.append("feDropShadow").attr("dx", 0).attr("dy", 0).attr("stdDeviation", 4).attr("flood-color", "#f38ba8").attr("flood-opacity", 0.6);

    const g = svg.append("g");

    const zoom = d3.zoom().scaleExtent([0.1, 4]).on("zoom", (event) => {{
        g.attr("transform", event.transform);
    }});
    svg.call(zoom);

    const link = g.append("g")
        .selectAll("line")
        .data(DATA.links)
        .join("line")
        .attr("class", d => {{
            const key = d.source.id + "|||" + d.target.id;
            return cycleEdges.has(key) ? "link cycle-link" : "link";
        }})
        .attr("stroke-width", d => cycleEdges.has(d.source.id + "|||" + d.target.id) ? 2.5 : 1.2);

    const node = g.append("g")
        .selectAll("g")
        .data(DATA.nodes)
        .join("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragStarted)
            .on("drag", dragged)
            .on("end", dragEnded));

    node.filter(d => {{
        const inCycle = DATA.cycles && DATA.cycles.some(c => c.includes(d.id));
        return inCycle;
    }}).append("circle")
        .attr("r", d => 4 + Math.sqrt(d.importedByCount || 1) * 2.5 + 5)
        .attr("fill", "none")
        .attr("stroke", "#f38ba8")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "4 2")
        .attr("opacity", 0.5);

    node.append("circle")
        .attr("r", d => 4 + Math.sqrt(d.importedByCount || 1) * 2.5)
        .attr("fill", d => d.color)
        .attr("stroke", d => d3.color(d.color).brighter(0.5));

    node.append("text")
        .attr("dx", 10)
        .attr("dy", 4)
        .text(d => d.label);

    node.on("mouseover", function(event, d) {{
        d3.select(this).select("circle").transition().duration(150).attr("r", d => (4 + Math.sqrt(d.importedByCount || 1) * 2.5) * 1.5);
        const tip = document.getElementById("tooltip");
        const inCycle = DATA.cycles && DATA.cycles.some(c => c.includes(d.id));
        const cycleWarn = inCycle ? '<br/><span style="color:#f38ba8">⚠ 存在循环依赖</span>' : '';
        tip.innerHTML = `<strong>${{d.label}}</strong><br/>${{d.purpose}}${{cycleWarn}}<br/>被 ${{d.importedByCount}} 个文件引用 · 依赖 ${{d.importsCount}} 个文件 · 符号引用 ${{d.crossRefsCount || 0}}`;
        tip.style.opacity = "1";
        tip.style.left = (event.pageX + 12) + "px";
        tip.style.top = (event.pageY - 28) + "px";
    }})
    .on("mousemove", function(event) {{
        const tip = document.getElementById("tooltip");
        tip.style.left = (event.pageX + 12) + "px";
        tip.style.top = (event.pageY - 28) + "px";
    }})
    .on("mouseout", function() {{
        d3.select(this).select("circle").transition().duration(150).attr("r", d => 4 + Math.sqrt(d.importedByCount || 1) * 2.5);
        document.getElementById("tooltip").style.opacity = "0";
    }})
    .on("click", function(event, d) {{
        event.stopPropagation();
        showDetail(d);
    }});

    svg.on("click", function() {{
        document.getElementById("detail").classList.remove("active");
    }});

    function showDetail(d) {{
        const detail = document.getElementById("detail");
        detail.classList.add("active");
        const inCycle = DATA.cycles && DATA.cycles.some(c => c.includes(d.id));
        const cycleWarn = inCycle ? '<span class="tag" style="background:#f38ba833;color:#f38ba8">循环依赖</span>' : '';
        const importsHtml = d.imports && d.imports.length > 0
            ? '<p style="margin-top:6px;"><strong>依赖:</strong></p><div class="dep-list">' + d.imports.map(i => '<span>' + i + '</span>').join('') + '</div>'
            : '<p style="margin-top:6px;"><strong>依赖:</strong> 无</p>';
        const importedByHtml = d.importedBy && d.importedBy.length > 0
            ? '<p style="margin-top:4px;"><strong>被引用:</strong></p><div class="dep-list">' + d.importedBy.map(i => '<span>' + i + '</span>').join('') + '</div>'
            : '<p style="margin-top:4px;"><strong>被引用:</strong> 无</p>';
        const crossRefsHtml = d.crossRefs && Object.keys(d.crossRefs).length > 0
            ? '<p style="margin-top:4px;"><strong>符号引用:</strong></p><div class="dep-list">' + Object.entries(d.crossRefs).map(([k, v]) => '<span>' + k + ' ← ' + (v||[]).join(', ') + '</span>').join('') + '</div>'
            : '<p style="margin-top:4px;"><strong>符号引用:</strong> 无</p>';
        const callTargetsHtml = d.callTargets && d.callTargets.length > 0
            ? '<p style="margin-top:4px;"><strong>调用目标:</strong></p><div class="dep-list">' + d.callTargets.map(t => '<span>' + t.context + ' (' + t.kind + ')</span>').join('') + '</div>'
            : '';
        const unusedHtml = d.unusedImports && d.unusedImports.length > 0
            ? '<p style="margin-top:4px;"><strong style="color:#e67e22">未使用导入:</strong></p><div class="dep-list">' + d.unusedImports.map(i => '<span style="color:#e67e22">' + i + '</span>').join('') + '</div>'
            : '';
        detail.innerHTML = `
            <h3>${{d.fullPath}}</h3>
            <p>${{cycleWarn}}<span class="tag" style="background:${{d.color}}33;color:${{d.color}}">${{d.layer}}</span>
            <span class="tag" style="background:#45475a">${{d.language}}</span></p>
            <p style="margin-top:8px;"><strong>功能:</strong> ${{d.purpose}}</p>
            <p><strong>代码行数:</strong> ${{d.lines}} · <strong>被引用:</strong> ${{d.importedByCount}} 次 · <strong>依赖:</strong> ${{d.importsCount}} 个 · <strong>符号引用:</strong> ${{d.crossRefsCount || 0}} · <strong>调用:</strong> ${{d.callTargetsCount || 0}}</p>
            ${{importsHtml}}
            ${{importedByHtml}}
            ${{crossRefsHtml}}
            ${{callTargetsHtml}}
            ${{unusedHtml}}
        `;
    }}

    const simulation = d3.forceSimulation(DATA.nodes)
        .force("link", d3.forceLink(DATA.links).id(d => d.id).distance(110))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(25));

    simulation.on("tick", () => {{
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
        node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    function dragStarted(event, d) {{
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }}
    function dragged(event, d) {{
        d.fx = event.x;
        d.fy = event.y;
    }}
    function dragEnded(event, d) {{
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }}

    const searchBox = document.getElementById("search-box");
    const filterCount = document.getElementById("filter-count");
    searchBox.addEventListener("input", function() {{
        const query = this.value.toLowerCase().trim();
        let matchCount = 0;
        node.each(function(d) {{
            const match = !query || d.id.toLowerCase().includes(query) || d.label.toLowerCase().includes(query);
            if (match) matchCount++;
            d3.select(this).classed("dimmed", !match);
        }});
        link.each(function(d) {{
            const match = !query || (d.source.id.toLowerCase().includes(query) || d.target.id.toLowerCase().includes(query));
            d3.select(this).classed("dimmed", !match);
        }});
        if (query) {{
            filterCount.textContent = `匹配 ${{matchCount}} 个文件`;
            filterCount.classList.add("visible");
        }} else {{
            filterCount.classList.remove("visible");
        }}
    }});

    document.getElementById("btn-svg").addEventListener("click", function() {{
        const serializer = new XMLSerializer();
        const svgEl = document.querySelector("#graph svg");
        const clone = svgEl.cloneNode(true);
        const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute("width", "100%");
        bg.setAttribute("height", "100%");
        bg.setAttribute("fill", "#11111b");
        clone.insertBefore(bg, clone.firstChild);
        const source = serializer.serializeToString(clone);
        const blob = new Blob([source], {{ type: "image/svg+xml" }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "dependency-graph.svg";
        a.click();
        URL.revokeObjectURL(url);
    }});

    document.getElementById("btn-png").addEventListener("click", function() {{
        const svgEl = document.querySelector("#graph svg");
        const serializer = new XMLSerializer();
        const clone = svgEl.cloneNode(true);
        const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute("width", width);
        bg.setAttribute("height", height);
        bg.setAttribute("fill", "#11111b");
        clone.insertBefore(bg, clone.firstChild);
        clone.setAttribute("width", width);
        clone.setAttribute("height", height);
        const source = serializer.serializeToString(clone);
        const canvas = document.createElement("canvas");
        canvas.width = width * 2;
        canvas.height = height * 2;
        const ctx = canvas.getContext("2d");
        ctx.scale(2, 2);
        const img = new Image();
        img.onload = function() {{
            ctx.drawImage(img, 0, 0, width, height);
            canvas.toBlob(function(blob) {{
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "dependency-graph.png";
                a.click();
                URL.revokeObjectURL(url);
            }});
        }};
        img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(source)));
    }});

    document.getElementById("btn-reset").addEventListener("click", function() {{
        svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity);
        searchBox.value = "";
        searchBox.dispatchEvent(new Event("input"));
    }});
}})();
</script>
</body>
</html>"""