from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from ..graph.dependency_graph import FileNode


class JavaParser:
    """Java / SpringBoot 专用解析器：解析包声明、import、类继承、接口实现、
    Spring 注解、方法调用、字段注入等。"""

    # 注释
    COMMENT_RE = re.compile(
        r"//.*?$|/\*[\s\S]*?\*/",
        re.MULTILINE,
    )

    # package 声明
    PACKAGE_RE = re.compile(r"package\s+([\w.]+)\s*;")

    # import 语句（包括 static import）
    IMPORT_RE = re.compile(r"import\s+((?:static\s+)?[\w.*]+)\s*;")

    # 类定义（public/private/default class/interface/enum/record）
    CLASS_RE = re.compile(
        r"(?:public\s+)?(?:abstract\s+)?(?:final\s+)?"
        r"(class|interface|enum|record)\s+(\w+)",
        re.MULTILINE,
    )

    # 继承、实现
    EXTENDS_RE = re.compile(r"extends\s+([\w.<>,\s]+?)(?:\s+implements|\s*\{)", re.MULTILINE)
    IMPLEMENTS_RE = re.compile(r"implements\s+([\w.<>,\s]+?)(?:\s*\{)", re.MULTILINE)

    # Spring 注解（用于功能推断）
    SPRING_ANNOTATIONS = [
        (re.compile(r"@RestController\b"), "REST 控制器"),
        (re.compile(r"@Controller\b"), "MVC 控制器"),
        (re.compile(r"@Service\b"), "业务服务"),
        (re.compile(r"@Repository\b"), "数据仓库"),
        (re.compile(r"@Component\b"), "Spring 组件"),
        (re.compile(r"@Configuration\b"), "配置类"),
        (re.compile(r"@SpringBootApplication\b"), "Spring Boot 入口"),
        (re.compile(r"@Entity\b"), "JPA 实体"),
        (re.compile(r"@Mapper\b"), "MyBatis 映射器"),
        (re.compile(r"@FeignClient\b"), "Feign 客户端"),
        (re.compile(r"@Aspect\b"), "AOP 切面"),
        (re.compile(r"@ControllerAdvice\b"), "全局异常处理"),
        (re.compile(r"@EnableScheduling\b"), "定时任务配置"),
        (re.compile(r"@Scheduled\b"), "定时任务"),
        (re.compile(r"@EventListener\b"), "事件监听"),
        (re.compile(r"@Transactional\b"), "事务"),
    ]

    # @Autowired / @Resource 字段注入
    AUTOWIRED_RE = re.compile(
        r"@(?:Autowired|Resource|Inject|Qualifier)\s*(?:\([^)]*\))?\s*\n?\s*"
        r"(?:private|public|protected)\s+(?:static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*;",
        re.MULTILINE,
    )

    # 方法定义（public/private/protected 返回类型 方法名(参数)）
    METHOD_RE = re.compile(
        r"(?:public|private|protected)\s+(?:static\s+)?(?:abstract\s+)?"
        r"(?:<[^>]+>\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)",
        re.MULTILINE,
    )

    # 方法调用：ClassName.methodName(...) 或 instance.methodName(...)
    METHOD_CALL_RE = re.compile(
        r"(?:^|[^\w])(\w+)\.(\w+)\s*\(",
        re.MULTILINE,
    )

    # new ClassName(...)
    NEW_RE = re.compile(r"new\s+(\w+)\s*\(", re.MULTILINE)

    def __init__(self, project_root: str) -> None:
        self._project_root = Path(project_root).resolve()
        self._source_roots: list[Path] = self._detect_source_roots()

    def _detect_source_roots(self) -> list[Path]:
        """检测 Maven/Gradle 源文件根目录。"""
        roots = []

        # 标准 Maven/Gradle 源目录
        std_roots = [
            "src/main/java",
            "src/test/java",
            "src/main/kotlin",
            "src/test/kotlin",
            "src/main/scala",
            "src/test/scala",
            "src/main/groovy",
            "src/test/groovy",
            "app/src/main/java",  # Android
        ]

        for sr in std_roots:
            candidate = self._project_root / sr
            if candidate.is_dir():
                roots.append(candidate)

        # 多模块项目检测
        pom = self._project_root / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text(encoding="utf-8")
                if "<modules>" in content:
                    mod_pattern = re.compile(r"<module>\s*([^<\s]+)\s*</module>")
                    for match in mod_pattern.finditer(content):
                        mod_name = match.group(1)
                        for sr in std_roots:
                            mod_sr = self._project_root / mod_name / sr
                            if mod_sr.is_dir():
                                roots.append(mod_sr)
            except (OSError, UnicodeDecodeError):
                pass

        # Gradle 多模块
        settings = self._project_root / "settings.gradle"
        if not settings.exists():
            settings = self._project_root / "settings.gradle.kts"
        if settings.exists():
            try:
                content = settings.read_text(encoding="utf-8")
                mod_pattern = re.compile(r"""(?:include|includeBuild)\s+['\":]\s*([^'":\s]+)\s*['":]""")
                for match in mod_pattern.finditer(content):
                    mod_name = match.group(1).replace(":", "/")
                    for sr in std_roots:
                        mod_sr = self._project_root / mod_name / sr
                        if mod_sr.is_dir():
                            roots.append(mod_sr)
            except (OSError, UnicodeDecodeError):
                pass

        # 如果没有检测到标准目录，回退到项目根目录 + 常见 Java 源文件夹
        if not roots:
            # 检查是否有包结构的目录（通过查找 java 文件来确定源根）
            for root_dir, dirs, files in os.walk(str(self._project_root)):
                # 限制扫描深度
                rel = Path(root_dir).relative_to(self._project_root)
                if len(rel.parts) > 6:
                    continue
                java_files = [f for f in files if f.endswith(".java")]
                if java_files and len(rel.parts) >= 1:
                    roots.append(Path(root_dir))
                    break
            if not roots:
                roots.append(self._project_root)

        return roots

    def _resolve_import(self, import_path: str, source_path: Path) -> Optional[str]:
        """将 import 语句解析为项目内的文件相对路径。"""
        if import_path.startswith("static "):
            import_path = import_path[7:]

        # 跳过 JDK/框架包
        if import_path.startswith(("java.", "javax.", "jakarta.", "org.springframework.",
                                    "org.apache.", "org.hibernate.", "com.fasterxml.",
                                    "org.slf4j", "lombok.", "ch.qos.logback",
                                    "org.mybatis.", "com.baomidou.", "org.junit",
                                    "org.mockito.", "org.assertj.", "com.google.common",
                                    "io.jsonwebtoken", "cn.hutool")):
            return None

        # 首先检测 package 声明以推断源根
        package_dir = None
        try:
            source_code = source_path.read_text(encoding="utf-8")
            pkg_match = self.PACKAGE_RE.search(source_code)
            if pkg_match:
                package_name = pkg_match.group(1)
                package_dir = package_name.replace(".", "/")
        except (OSError, UnicodeDecodeError):
            pass

        parts = import_path.split(".")
        # 移除最后的通配符 import（如 com.example.* -> com.example）
        if parts[-1] == "*":
            parts = parts[:-1]

        # 方法 1：从源文件所在目录按包名深度反向查找
        if package_dir:
            source_rel = str(source_path.parent.relative_to(self._project_root)).replace(os.sep, "/")
            if source_rel.endswith(package_dir):
                # 源文件在正确的包路径下，源根就是 package_dir 之上的目录
                src_root_rel = source_rel[:-len(package_dir)].rstrip("/")
                # 在这个源根下查找导入的文件
                for depth in range(len(parts), 0, -1):
                    candidate = self._project_root / src_root_rel / "/".join(parts[:depth]) / ".java"
                    if candidate.exists():
                        try:
                            return str(candidate.relative_to(self._project_root)).replace(os.sep, "/")
                        except ValueError:
                            pass
                    # 也尝试直接文件匹配
                    candidate_file = self._project_root / src_root_rel / f"{'/'.join(parts[:depth])}.java"
                    if candidate_file.exists():
                        try:
                            return str(candidate_file.relative_to(self._project_root)).replace(os.sep, "/")
                        except ValueError:
                            pass

        # 方法 2：遍历所有检测到的源根
        for src_root in self._source_roots:
            for depth in range(len(parts), 0, -1):
                candidate = src_root / f"{'/'.join(parts[:depth])}.java"
                resolved = self._to_relative(candidate)
                if resolved:
                    return resolved
                # 也尝试作为目录 + 通配符（虽然没有具体文件名）
                candidate_dir = src_root / "/".join(parts[:depth])
                if candidate_dir.is_dir():
                    pass  # 通配符导入，标记为整个目录

        # 方法 3：从源文件所在目录查找
        source_dir = source_path.parent
        for depth in range(len(parts), 0, -1):
            candidate = source_dir / f"{'/'.join(parts[:depth])}.java"
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

    def parse_file(self, file_path: str) -> Optional[FileNode]:
        abs_path = Path(file_path).resolve()
        if not abs_path.exists() or abs_path.suffix != ".java":
            return None

        try:
            source_code = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

        cleaned = self.COMMENT_RE.sub("", source_code)

        imports = self._extract_imports(cleaned, abs_path)
        exports = self._extract_exports(cleaned)
        purpose = self._extract_purpose(cleaned)
        cross_refs = self._extract_cross_refs(cleaned, abs_path)
        call_targets = self._extract_call_targets(cleaned, abs_path, imports)

        return FileNode(
            path=str(abs_path),
            relative_path=str(abs_path.relative_to(self._project_root)).replace(os.sep, "/"),
            language="java",
            purpose=purpose,
            purpose_source="static",
            imports=imports,
            exports=exports,
            cross_refs=cross_refs,
            call_targets=call_targets,
            unused_imports=[],
            lines=len(source_code.splitlines()),
        )

    def _extract_imports(self, source: str, source_path: Path) -> list[str]:
        """提取并解析 import 语句。"""
        imports: set[str] = set()

        for match in self.IMPORT_RE.finditer(source):
            import_path = match.group(1)
            # 跳过通配符导入的符号追踪（但仍解析为依赖）
            if import_path.endswith(".*"):
                resolved = self._resolve_import(import_path[:-2], source_path)
                if resolved:
                    imports.add(resolved)
                continue

            resolved = self._resolve_import(import_path, source_path)
            if resolved:
                imports.add(resolved)
                continue

            # 未解析到文件的 import，可能引用的是类而非文件路径
            # 提取类名，尝试在源根中查找
            parts = import_path.split(".")
            class_name = parts[-1] if parts else ""
            if class_name and class_name[0].isupper():
                for src_root in self._source_roots:
                    if self._find_class_in_root(src_root, class_name, imports):
                        break

        return sorted(imports)

    def _find_class_in_root(self, src_root: Path, class_name: str, imports: set[str]) -> bool:
        """在源根目录下查找指定类名的文件。"""
        try:
            for root_dir, dirs, files in os.walk(str(src_root)):
                # 限制深度
                rel = Path(root_dir).relative_to(src_root)
                if len(rel.parts) > 12:
                    continue
                if f"{class_name}.java" in files:
                    candidate = Path(root_dir) / f"{class_name}.java"
                    resolved = self._to_relative(candidate)
                    if resolved:
                        imports.add(resolved)
                        return True
        except (OSError, ValueError):
            pass
        return False

    def _extract_exports(self, source: str) -> list[str]:
        """提取类、接口、枚举等导出符号。"""
        exports: list[str] = []

        for match in self.CLASS_RE.finditer(source):
            exports.append(match.group(2))

        # 公共方法
        for match in self.METHOD_RE.finditer(source):
            method_name = match.group(2)
            if method_name not in exports:
                exports.append(method_name)

        return exports

    def _extract_purpose(self, source: str) -> str:
        """根据 Spring 注解和类声明推断功能。"""
        purposes: list[str] = []

        # 检测 Spring 注解
        for pattern, desc in self.SPRING_ANNOTATIONS:
            if pattern.search(source):
                purposes.append(desc)

        if purposes:
            return " | ".join(purposes)

        # 根据类类型推断
        class_match = self.CLASS_RE.search(source)
        if class_match:
            class_type = class_match.group(1)
            class_name = class_match.group(2)

            if class_type == "interface":
                return f"接口定义 ({class_name})"
            elif class_type == "enum":
                return f"枚举定义 ({class_name})"
            elif class_type == "record":
                return f"数据记录 ({class_name})"
            elif class_name.endswith("Controller"):
                return "控制器"
            elif class_name.endswith("Service") or class_name.endswith("ServiceImpl"):
                return "业务服务"
            elif class_name.endswith("Repository") or class_name.endswith("DAO") or class_name.endswith("Mapper"):
                return "数据访问"
            elif class_name.endswith("Entity") or class_name.endswith("Model") or class_name.endswith("DTO") or class_name.endswith("VO"):
                return "数据模型"
            elif class_name.endswith("Config") or class_name.endswith("Configuration"):
                return "配置类"
            elif class_name.endswith("Util") or class_name.endswith("Utils") or class_name.endswith("Helper"):
                return "工具类"
            elif class_name.endswith("Filter") or class_name.endswith("Interceptor"):
                return "过滤器/拦截器"
            elif class_name.endswith("Handler"):
                return "处理器"
            elif class_name.endswith("Exception"):
                return "异常定义"
            elif class_name.endswith("Application"):
                return "应用入口"
            else:
                return f"Java 类 ({class_name})"

        return "Java 文件"

    def _extract_cross_refs(self, source: str, source_path: Path) -> dict[str, list[str]]:
        """提取跨文件符号引用。"""
        cross_refs: dict[str, list[str]] = {}

        # 建立 import -> relative_path 映射
        symbol_map: dict[str, str] = {}
        for match in self.IMPORT_RE.finditer(source):
            import_path = match.group(1)
            if import_path.endswith(".*"):
                continue
            class_name = import_path.split(".")[-1]
            resolved = self._resolve_import(import_path, source_path)
            if resolved:
                symbol_map[class_name] = resolved

        if not symbol_map:
            return cross_refs

        # 检测类名在代码中的使用
        # 排除 import、package 行
        exclude_lines: set[int] = set()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "package ")):
                exclude_lines.add(i)

        for symbol, resolved_path in symbol_map.items():
            usage_count = 0
            for i, line in enumerate(lines):
                if i in exclude_lines:
                    continue
                # 检查符号是否作为词出现在该行
                if re.search(r"\b" + re.escape(symbol) + r"\b", line):
                    usage_count += 1

            if usage_count > 0:
                if resolved_path not in cross_refs:
                    cross_refs[resolved_path] = []
                if symbol not in cross_refs[resolved_path]:
                    cross_refs[resolved_path].append(symbol)

        # 检测 @Autowired / @Resource 字段注入的类引用
        for match in self.AUTOWIRED_RE.finditer(source):
            field_type = match.group(1)
            # 移除泛型参数
            if "<" in field_type:
                field_type = field_type[:field_type.index("<")]
            if field_type in symbol_map:
                resolved = symbol_map[field_type]
                if resolved not in cross_refs:
                    cross_refs[resolved] = []
                if field_type not in cross_refs[resolved]:
                    cross_refs[resolved].append(f"@{field_type}")

        return cross_refs

    def _extract_call_targets(self, source: str, source_path: Path, imports: list[str]) -> list[dict]:
        """提取方法调用目标。"""
        call_targets: list[dict] = []

        # 建立 class_name -> relative_path 映射
        symbol_map: dict[str, str] = {}
        for match in self.IMPORT_RE.finditer(source):
            import_path = match.group(1)
            if import_path.endswith(".*"):
                continue
            class_name = import_path.split(".")[-1]
            resolved = self._resolve_import(import_path, source_path)
            if resolved:
                symbol_map[class_name] = resolved

        lines = source.split("\n")
        exclude_pattern = re.compile(r"^\s*(?:import|package)\s")

        # 建立变量名 -> 类名映射（用于解析 instance.method() 调用）
        var_to_type: dict[str, str] = {}

        # 1. @Autowired/@Resource/@Inject private ClassName varName;
        field_decl = re.compile(
            r"(?:@\w+\s*(?:\([^)]*\))?\s*)?"  # 可选的注解
            r"(?:private|public|protected)\s+(?:static\s+)?(?:final\s+)?"
            r"(\w+(?:<[^>]+>)?)\s+(\w+)\s*[=;]",
            re.MULTILINE,
        )
        for match in field_decl.finditer(source):
            field_type = match.group(1)
            field_name = match.group(2)
            if "<" in field_type:
                field_type = field_type[:field_type.index("<")]
            if field_type in symbol_map:
                var_to_type[field_name] = field_type

        # 2. 构造函数参数注入
        constructor_param = re.compile(
            r"(?:private|public|protected)\s+(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)[,\s)]",
            re.MULTILINE,
        )
        in_constructor = False
        for line in lines:
            if re.search(r"public\s+\w+\s*\(", line):
                in_constructor = True
                # 提取构造函数参数
                param_match = re.search(r"\(([^)]*)\)", line)
                if param_match:
                    params = param_match.group(1)
                    for param in params.split(","):
                        param = param.strip()
                        parts = param.split()
                        if len(parts) >= 2:
                            ptype = parts[-2]
                            pname = parts[-1]
                            if ptype in symbol_map:
                                var_to_type[pname] = ptype
                continue
            if in_constructor and "{" in line:
                in_constructor = False

        # 3. 局部变量声明: ClassName varName = ...
        local_var = re.compile(
            r"\b(\w+(?:<[^>]+>)?)\s+(\w+)\s*=\s*(?:new\s+\w+|[^;]+)",
        )
        for i, line in enumerate(lines):
            if exclude_pattern.match(line):
                continue
            for match in local_var.finditer(line):
                ltype = match.group(1)
                lname = match.group(2)
                if "<" in ltype:
                    ltype = ltype[:ltype.index("<")]
                if ltype in symbol_map and ltype[0].isupper():
                    var_to_type[lname] = ltype

        # 检测 ClassName.methodName(...) 调用
        for i, line in enumerate(lines):
            if exclude_pattern.match(line):
                continue
            for match in self.METHOD_CALL_RE.finditer(line):
                obj_name = match.group(1)
                method_name = match.group(2)

                # 跳过关键字和原始类型
                if obj_name in ("if", "else", "for", "while", "return", "new",
                                "this", "super", "true", "false", "null",
                                "int", "long", "double", "float", "boolean",
                                "void", "String", "Integer", "Long", "Double",
                                "Boolean", "List", "Map", "Set", "Optional",
                                "class", "System", "Math", "Objects", "Arrays",
                                "Collections", "Pattern", "Stream", "Collectors"):
                    continue

                target_file = None
                if obj_name in symbol_map:
                    target_file = symbol_map[obj_name]
                elif obj_name in var_to_type:
                    resolved_type = var_to_type[obj_name]
                    if resolved_type in symbol_map:
                        target_file = symbol_map[resolved_type]

                if target_file:
                    call_targets.append({
                        "file": target_file,
                        "symbol": method_name,
                        "kind": "call",
                        "context": f"{obj_name}.{method_name}()",
                    })

        # 检测 new ClassName(...) 实例化
        for match in self.NEW_RE.finditer(source):
            class_name = match.group(1)
            if class_name in symbol_map:
                call_targets.append({
                    "file": symbol_map[class_name],
                    "symbol": class_name,
                    "kind": "instantiate",
                    "context": f"new {class_name}()",
                })

        # 检测 extends 继承
        extends_match = self.EXTENDS_RE.search(source)
        if extends_match:
            parent = extends_match.group(1).strip()
            for p in parent.split(","):
                p = p.strip()
                if p in symbol_map:
                    call_targets.append({
                        "file": symbol_map[p],
                        "symbol": p,
                        "kind": "extends",
                        "context": f"extends {p}",
                    })

        # 检测 implements 实现
        impl_match = self.IMPLEMENTS_RE.search(source)
        if impl_match:
            interfaces = impl_match.group(1).strip()
            for iface in interfaces.split(","):
                iface = iface.strip()
                if iface in symbol_map:
                    call_targets.append({
                        "file": symbol_map[iface],
                        "symbol": iface,
                        "kind": "implements",
                        "context": f"implements {iface}",
                    })

        # 检测 @Autowired 构造函数注入
        autowired_constructor = re.compile(
            r"@Autowired\s*\n?\s*public\s+\w+\s*\(([^)]*)\)",
            re.MULTILINE,
        )
        for match in autowired_constructor.finditer(source):
            params = match.group(1)
            for param in params.split(","):
                param = param.strip()
                if not param:
                    continue
                parts = param.split()
                if len(parts) >= 2:
                    param_type = parts[-2] if len(parts) >= 2 else parts[0]
                    param_name = parts[-1]
                    if param_type in symbol_map:
                        call_targets.append({
                            "file": symbol_map[param_type],
                            "symbol": param_name,
                            "kind": "inject",
                            "context": f"@Autowired {param_type} {param_name}",
                        })

        return call_targets

    def get_source_roots(self) -> list[str]:
        """返回检测到的源根目录（相对路径）。"""
        result = []
        for sr in self._source_roots:
            try:
                result.append(str(sr.relative_to(self._project_root)).replace(os.sep, "/"))
            except ValueError:
                result.append(str(sr).replace(os.sep, "/"))
        return result