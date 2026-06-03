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

        graph_json = json.dumps(
            {"nodes": nodes_data, "links": links_data, "cycles": cycles_data},
            ensure_ascii=False,
        )
        stats_json = json.dumps(stats, ensure_ascii=False)

        html = self._render_html(graph_json, stats_json)

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

    def _render_html(self, graph_json: str, stats_json: str) -> str:
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
</div>
<div id="graph"></div>
</div>
<div class="tooltip" id="tooltip"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = {graph_json};
const STATS = {stats_json};

(function() {{
    function renderStats() {{
        const grid = document.getElementById("stats-grid");
        const cycleClass = STATS.cycles > 0 ? ' warn' : '';
        grid.innerHTML = `
            <div class="stat-card"><div class="num">${{STATS.total_files}}</div><div class="lbl">总文件数</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_lines}}</div><div class="lbl">总代码行</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_imports}}</div><div class="lbl">依赖关系</div></div>
            <div class="stat-card"><div class="num">${{STATS.total_xrefs}}</div><div class="lbl">符号引用</div></div>
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
        detail.innerHTML = `
            <h3>${{d.fullPath}}</h3>
            <p>${{cycleWarn}}<span class="tag" style="background:${{d.color}}33;color:${{d.color}}">${{d.layer}}</span>
            <span class="tag" style="background:#45475a">${{d.language}}</span></p>
            <p style="margin-top:8px;"><strong>功能:</strong> ${{d.purpose}}</p>
            <p><strong>代码行数:</strong> ${{d.lines}} · <strong>被引用:</strong> ${{d.importedByCount}} 次 · <strong>依赖:</strong> ${{d.importsCount}} 个 · <strong>符号引用:</strong> ${{d.crossRefsCount || 0}}</p>
            ${{importsHtml}}
            ${{importedByHtml}}
            ${{crossRefsHtml}}
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