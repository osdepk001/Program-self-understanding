"""
API 端点检测器：自动发现项目中的所有 REST API 端点。
支持 Spring Boot, Flask, FastAPI, Express, Gin, Django, Laravel 等框架。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ApiEndpoint:
    """单个 API 端点的描述。"""

    def __init__(self, method: str, path: str, handler: str, file_path: str,
                 line: int = 0, description: str = ""):
        self.method = method
        self.path = path
        self.handler = handler
        self.file_path = file_path
        self.line = line
        self.description = description

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "path": self.path,
            "handler": self.handler,
            "file_path": self.file_path,
            "line": self.line,
            "description": self.description,
        }


class ApiEndpointDetector:
    """检测项目中的 API 端点。"""

    # HTTP 方法颜色
    METHOD_COLORS = {
        "GET": "#198754", "POST": "#0d6efd", "PUT": "#fd7e14",
        "DELETE": "#dc3545", "PATCH": "#6f42c1", "HEAD": "#6c757d",
        "OPTIONS": "#6c757d", "ANY": "#adb5bd",
    }

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._endpoints: list[ApiEndpoint] = []

    def detect(self, files: list[Path]) -> list[ApiEndpoint]:
        """扫描所有文件，检测 API 端点。"""
        for file_path in files:
            ext = file_path.suffix.lower()
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if ext == ".java":
                self._detect_java(file_path, content)
            elif ext == ".py":
                self._detect_python(file_path, content)
            elif ext in (".js", ".mjs", ".cjs"):
                self._detect_javascript(file_path, content)
            elif ext in (".ts", ".tsx"):
                self._detect_typescript(file_path, content)
            elif ext == ".php":
                self._detect_php(file_path, content)
            elif ext == ".go":
                self._detect_go(file_path, content)
            elif ext == ".rb":
                self._detect_ruby(file_path, content)
            elif ext in (".cs",):
                self._detect_csharp(file_path, content)

        return self._endpoints

    # ==================== Java / Spring Boot ====================

    def _detect_java(self, file_path: Path, content: str) -> None:
        """检测 Spring Boot 端点注解。"""
        # 类级别 @RequestMapping
        class_base = ""
        class_m = re.search(r'@RequestMapping\s*\(\s*["\']?([^"\')\s]+)', content)
        if class_m:
            class_base = class_m.group(1).rstrip("/")

        # 方法级别注解 - 支持有参数和无参数两种形式
        patterns = [
            (r'@GetMapping\s*\((?:[^)]*?["\']?([^"\')\s]*))?\)', "GET"),
            (r'@PostMapping\s*\((?:[^)]*?["\']?([^"\')\s]*))?\)', "POST"),
            (r'@PutMapping\s*\((?:[^)]*?["\']?([^"\')\s]*))?\)', "PUT"),
            (r'@DeleteMapping\s*\((?:[^)]*?["\']?([^"\')\s]*))?\)', "DELETE"),
            (r'@PatchMapping\s*\((?:[^)]*?["\']?([^"\')\s]*))?\)', "PATCH"),
            (r'@RequestMapping\s*\(\s*method\s*=\s*\w+\.(GET|POST|PUT|DELETE|PATCH)\b[^)]*?(?:value|path)\s*=\s*["\']([^"\']*)', None),
        ]

        # 无括号的注解 (如 @GetMapping 单独一行)
        bracketless = [
            (r'@GetMapping\b(?!\s*\()', "GET"),
            (r'@PostMapping\b(?!\s*\()', "POST"),
            (r'@PutMapping\b(?!\s*\()', "PUT"),
            (r'@DeleteMapping\b(?!\s*\()', "DELETE"),
            (r'@PatchMapping\b(?!\s*\()', "PATCH"),
        ]
        for bl_pattern, bl_method in bracketless:
            for m in re.finditer(bl_pattern, content, re.IGNORECASE):
                full_path = class_base or "/"
                handler = self._find_method_name(content, m.start())
                self._endpoints.append(ApiEndpoint(
                    method=bl_method, path=full_path, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description=f"Spring Boot {bl_method}"
                ))

        for pattern, default_method in patterns:
            for m in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                if default_method:
                    path_value = m.group(1) or ""
                    path_value = path_value.strip().strip('"').strip("'")
                    method = default_method
                else:
                    method = m.group(1).upper()
                    path_value = m.group(2) if m.lastindex >= 2 else ""

                full_path = self._join_path(class_base, path_value)
                # 找方法名
                handler = self._find_method_name(content, m.start())

                self._endpoints.append(ApiEndpoint(
                    method=method, path=full_path, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description=f"Spring Boot {method}"
                ))

        # JAX-RS 注解 (Jersey, Quarkus)
        jaxrs_patterns = [
            (r'@GET\b', "GET"), (r'@POST\b', "POST"), (r'@PUT\b', "PUT"),
            (r'@DELETE\b', "DELETE"), (r'@PATCH\b', "PATCH"),
            (r'@HEAD\b', "HEAD"), (r'@OPTIONS\b', "OPTIONS"),
        ]

        for pattern, method in jaxrs_patterns:
            for m in re.finditer(pattern, content):
                # 找对应的 @Path
                path_match = re.search(r'@Path\s*\(\s*["\']([^"\']+)', content[m.start():m.start() + 200])
                path_value = path_match.group(1) if path_match else ""
                full_path = self._join_path(class_base, path_value)
                handler = self._find_method_name(content, m.start())
                self._endpoints.append(ApiEndpoint(
                    method=method, path=full_path, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="JAX-RS"
                ))

    # ==================== Python ====================

    def _detect_python(self, file_path: Path, content: str) -> None:
        """检测 Flask / FastAPI / Django 端点。"""
        # Flask: @app.route('/path', methods=['GET','POST']) 或 @bp.route(...)
        flask_patterns = [
            r"@\w+\.route\s*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*methods\s*=\s*\[([^\]]+)\])?",
            r"@\w+\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
        ]

        for m in re.finditer(flask_patterns[0], content):
            path_value = m.group(1)
            methods_str = m.group(2)
            methods = self._parse_methods(methods_str) if methods_str else ["GET"]
            handler = self._find_python_func(content, m.start())
            for method in methods:
                self._endpoints.append(ApiEndpoint(
                    method=method.upper(), path=path_value, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="Flask"
                ))

        for m in re.finditer(flask_patterns[1], content):
            method = m.group(1).upper()
            path_value = m.group(2)
            handler = self._find_python_func(content, m.start())
            self._endpoints.append(ApiEndpoint(
                method=method, path=path_value, handler=handler,
                file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                description="Flask"
            ))

        # FastAPI: @app.get('/path'), @router.post('/path')
        fastapi_methods = ["get", "post", "put", "delete", "patch", "head", "options"]
        for method_name in fastapi_methods:
            for m in re.finditer(rf"@\w+\.{method_name}\s*\(\s*['\"]([^'\"]+)['\"]", content):
                path_value = m.group(1)
                handler = self._find_python_func(content, m.start())
                self._endpoints.append(ApiEndpoint(
                    method=method_name.upper(), path=path_value, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="FastAPI"
                ))

        # Django: urlpatterns / path() / re_path()
        django_patterns = re.finditer(
            r"(?:path|re_path|url)\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*(\w+)",
            content
        )
        for m in django_patterns:
            path_value = m.group(1)
            view_name = m.group(2)
            self._endpoints.append(ApiEndpoint(
                method="ANY", path=path_value, handler=view_name,
                file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                description="Django URL"
            ))

    # ==================== JavaScript / Express ====================

    def _detect_javascript(self, file_path: Path, content: str) -> None:
        """检测 Express / Koa 端点。"""
        # Express: app.get('/path', handler), router.post('/path', handler)
        express_methods = ["get", "post", "put", "delete", "patch", "head", "options", "all", "use"]

        for method_name in express_methods:
            method_display = "ANY" if method_name in ("all", "use") else method_name.upper()
            for m in re.finditer(
                rf"(?:app|router|this)\.{method_name}\s*\(\s*['\"`]([^'\"`]+)['\"`]",
                content
            ):
                path_value = m.group(1)
                self._endpoints.append(ApiEndpoint(
                    method=method_display, path=path_value, handler="handler",
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="Express"
                ))

        # Koa: router.get('/path', handler)
        for m in re.finditer(r"router\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]", content):
            self._endpoints.append(ApiEndpoint(
                method=m.group(1).upper(), path=m.group(2), handler="handler",
                file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                description="Koa"
            ))

    # ==================== TypeScript / NestJS ====================

    def _detect_typescript(self, file_path: Path, content: str) -> None:
        """检测 TypeScript / NestJS 端点。"""
        # NestJS decorators: @Get(), @Post(), @Get(':id')
        nest_methods = ["Get", "Post", "Put", "Delete", "Patch", "Head", "Options", "All"]
        # 类级别 @Controller('base')
        controller_base = ""
        ctrl_m = re.search(r"@Controller\s*\(\s*['\"`]([^'\"`]*)['\"`]", content)
        if ctrl_m:
            controller_base = ctrl_m.group(1).rstrip("/")

        for method_name in nest_methods:
            method_display = "ANY" if method_name == "All" else method_name.upper()
            for m in re.finditer(rf"@{method_name}\s*\(\s*['\"`]([^'\"`]*)['\"`]", content):
                path_value = m.group(1)
                full_path = self._join_path(controller_base, path_value)
                handler = self._find_method_name(content, m.start()) or self._find_ts_method(content, m.start())
                self._endpoints.append(ApiEndpoint(
                    method=method_display, path=full_path, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="NestJS"
                ))

        # Also check Express patterns (some TS projects use Express)
        self._detect_javascript(file_path, content)

    # ==================== PHP / Laravel ====================

    def _detect_php(self, file_path: Path, content: str) -> None:
        """检测 PHP / Laravel 端点。"""
        # Laravel Route::get('/path', [Controller::class, 'method'])
        laravel_methods = {
            "get": "GET", "post": "POST", "put": "PUT", "delete": "DELETE",
            "patch": "PATCH", "any": "ANY", "match": "ANY",
            "resource": "CRUD", "apiResource": "CRUD",
        }
        for m in re.finditer(
            r"Route::(get|post|put|delete|patch|any|match|resource|apiResource)\s*\(\s*['\"]([^'\"]+)['\"]",
            content
        ):
            method_name = m.group(1).lower()
            method = laravel_methods.get(method_name, "GET")
            path_value = m.group(2)
            # 尝试提取处理器
            handler_match = re.search(
                r"['\"]" + re.escape(path_value) + r"['\"]\s*,\s*\[?['\"]?(\w+(?:@\w+)?)",
                content[m.start():m.start() + 150]
            )
            handler = handler_match.group(1) if handler_match else ""
            self._endpoints.append(ApiEndpoint(
                method=method, path=path_value, handler=handler,
                file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                description="Laravel"
            ))

        # Symfony: #[Route('/path', methods: ['GET'])] or @Route("/path")
        for m in re.finditer(
            r"#\[Route\s*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*methods\s*:\s*\[([^\]]+)\])?",
            content
        ):
            path_value = m.group(1)
            methods_str = m.group(2)
            methods = self._parse_methods(methods_str) if methods_str else ["GET"]
            handler = self._find_php_method(content, m.start())
            for method in methods:
                self._endpoints.append(ApiEndpoint(
                    method=method.upper(), path=path_value, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="Symfony"
                ))

    # ==================== Go / Gin ====================

    def _detect_go(self, file_path: Path, content: str) -> None:
        """检测 Go / Gin / Echo 端点。"""
        # Gin: r.GET("/path", handler), router.POST("/path", handler)
        gin_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "Any"]
        for method in gin_methods:
            method_display = "ANY" if method == "Any" else method
            for m in re.finditer(rf"\.{method}\s*\(\s*\"([^\"]+)\"\s*,\s*(\w+)", content):
                self._endpoints.append(ApiEndpoint(
                    method=method_display, path=m.group(1), handler=m.group(2),
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="Gin"
                ))

        # Echo: e.GET("/path", handler)
        for m in re.finditer(r"\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*\"([^\"]+)\"\s*,\s*(\w+)", content):
            self._endpoints.append(ApiEndpoint(
                method=m.group(1), path=m.group(2), handler=m.group(3),
                file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                description="Echo"
            ))

    # ==================== Ruby / Rails ====================

    def _detect_ruby(self, file_path: Path, content: str) -> None:
        """检测 Ruby / Rails 端点。"""
        # Rails routes: get '/path', to: 'controller#action'
        for m in re.finditer(
            r"(get|post|put|patch|delete)\s+['\"]([^'\"]+)['\"],?\s*(?:to:\s*['\"]?([^'\"]+)['\"]?)?",
            content
        ):
            self._endpoints.append(ApiEndpoint(
                method=m.group(1).upper(), path=m.group(2), handler=m.group(3) or "",
                file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                description="Rails"
            ))

    # ==================== C# / ASP.NET ====================

    def _detect_csharp(self, file_path: Path, content: str) -> None:
        """检测 C# / ASP.NET 端点。"""
        # [HttpGet], [HttpPost], [Route("api/users")]
        method_map = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT",
                      "HttpDelete": "DELETE", "HttpPatch": "PATCH"}

        controller_route = ""
        route_m = re.search(r'\[Route\s*\(\s*"([^"]+)"\)\]', content)
        if route_m:
            controller_route = route_m.group(1).rstrip("/")

        for attr, method in method_map.items():
            for m in re.finditer(rf'\[{attr}\s*(?:\(\s*"([^"]*)"\))?\]', content):
                path_value = m.group(1) or ""
                full_path = self._join_path(controller_route, path_value)
                handler = self._find_method_name(content, m.start())
                self._endpoints.append(ApiEndpoint(
                    method=method, path=full_path, handler=handler,
                    file_path=self._relative(file_path), line=self._line_of(content, m.start()),
                    description="ASP.NET"
                ))

    # ==================== Helpers ====================

    def _relative(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(self._root)).replace("\\", "/")
        except ValueError:
            return str(file_path)

    @staticmethod
    def _join_path(base: str, sub: str) -> str:
        """拼接基础路径和子路径。"""
        if not sub:
            return base or "/"
        if not base:
            return sub if sub.startswith("/") else "/" + sub
        base = base.rstrip("/")
        sub = sub if sub.startswith("/") else "/" + sub
        result = base + sub
        return result if result else "/"

    @staticmethod
    def _parse_methods(methods_str: str) -> list[str]:
        """解析 methods=['GET','POST'] 字符串。"""
        methods = re.findall(r"['\"](\w+)['\"]", methods_str)
        return methods if methods else ["GET"]

    @staticmethod
    def _find_method_name(content: str, pos: int) -> str:
        """在注解后查找方法名。"""
        chunk = content[pos:pos + 300]
        m = re.search(r'\b(?:public|private|protected|static|async)?\s*(?:[\w<>[\],\s]+\s+)?(\w+)\s*\(', chunk)
        return m.group(1) if m else ""

    @staticmethod
    def _find_ts_method(content: str, pos: int) -> str:
        chunk = content[pos:pos + 300]
        m = re.search(r'(?:async\s+)?(\w+)\s*\(', chunk)
        return m.group(1) if m else ""

    @staticmethod
    def _find_python_func(content: str, pos: int) -> str:
        chunk = content[pos:pos + 300]
        m = re.search(r'(?:async\s+)?def\s+(\w+)\s*\(', chunk)
        return m.group(1) if m else ""

    @staticmethod
    def _find_php_method(content: str, pos: int) -> str:
        chunk = content[pos:pos + 300]
        m = re.search(r'function\s+(\w+)\s*\(', chunk)
        return m.group(1) if m else ""

    @staticmethod
    def _line_of(content: str, pos: int) -> int:
        return content[:pos].count("\n") + 1


def build_endpoints_summary(endpoints: list[ApiEndpoint]) -> dict[str, Any]:
    """构建端点汇总数据。"""
    by_method: dict[str, int] = {}
    by_file: dict[str, list[dict]] = {}
    total = len(endpoints)

    for ep in endpoints:
        by_method[ep.method] = by_method.get(ep.method, 0) + 1
        if ep.file_path not in by_file:
            by_file[ep.file_path] = []
        by_file[ep.file_path].append(ep.to_dict())

    # 找到 API 最多的文件
    top_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)[:5]

    return {
        "total": total,
        "by_method": by_method,
        "top_files": [{"file": f, "count": len(eps)} for f, eps in top_files],
        "endpoints": [e.to_dict() for e in endpoints],
    }