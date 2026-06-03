"""
数据库模型分析器：提取 Entity/Model 类，展示表结构、字段、关联关系。
支持 JPA/Hibernate, Django ORM, SQLAlchemy, TypeORM, Prisma, GORM 等。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class DbField:
    """数据库字段。"""

    def __init__(self, name: str, field_type: str = "", nullable: bool = True,
                 primary_key: bool = False, default_value: str = "",
                 max_length: int = 0, is_relation: bool = False,
                 relation_type: str = "", relation_target: str = ""):
        self.name = name
        self.field_type = field_type
        self.nullable = nullable
        self.primary_key = primary_key
        self.default_value = default_value
        self.max_length = max_length
        self.is_relation = is_relation
        self.relation_type = relation_type
        self.relation_target = relation_target

    def to_dict(self) -> dict:
        return {
            "name": self.name, "type": self.field_type,
            "nullable": self.nullable, "primary_key": self.primary_key,
            "default": self.default_value, "max_length": self.max_length,
            "is_relation": self.is_relation,
            "relation_type": self.relation_type,
            "relation_target": self.relation_target,
        }


class DbModel:
    """数据库模型（表）。"""

    def __init__(self, table_name: str, class_name: str, file_path: str,
                 line: int = 0, orm: str = ""):
        self.table_name = table_name
        self.class_name = class_name
        self.file_path = file_path
        self.line = line
        self.orm = orm
        self.fields: list[DbField] = []

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "class_name": self.class_name,
            "file_path": self.file_path,
            "line": self.line,
            "orm": self.orm,
            "fields": [f.to_dict() for f in self.fields],
            "field_count": len(self.fields),
        }


class DbModelAnalyzer:
    """分析数据库模型。"""

    # Java 类型 → SQL 类型映射
    JAVA_TYPE_MAP = {
        "String": "VARCHAR", "Integer": "INTEGER", "int": "INTEGER",
        "Long": "BIGINT", "long": "BIGINT", "Double": "DOUBLE", "double": "DOUBLE",
        "Float": "FLOAT", "float": "FLOAT", "Boolean": "BOOLEAN", "boolean": "BOOLEAN",
        "BigDecimal": "DECIMAL", "Date": "DATE", "LocalDate": "DATE",
        "LocalDateTime": "TIMESTAMP", "Timestamp": "TIMESTAMP", "byte[]": "BLOB",
        "UUID": "UUID", "Enum": "VARCHAR", "BigInteger": "BIGINT",
    }

    # Python 类型 → SQL 类型映射
    PYTHON_TYPE_MAP = {
        "str": "VARCHAR", "int": "INTEGER", "float": "FLOAT",
        "bool": "BOOLEAN", "bytes": "BLOB", "datetime": "TIMESTAMP",
        "date": "DATE", "Decimal": "DECIMAL", "UUID": "UUID",
        "dict": "JSON", "list": "JSON", "set": "JSON",
    }

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._models: list[DbModel] = []

    def analyze(self, files: list[Path]) -> list[DbModel]:
        for file_path in files:
            ext = file_path.suffix.lower()
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if ext == ".java":
                self._analyze_java(file_path, content)
            elif ext == ".py":
                self._analyze_python(file_path, content)
            elif ext in (".ts", ".tsx"):
                self._analyze_typescript(file_path, content)
            elif ext in (".js", ".jsx"):
                self._analyze_javascript(file_path, content)
            elif ext == ".go":
                self._analyze_go(file_path, content)
            elif ext == ".php":
                self._analyze_php(file_path, content)
            elif ext == ".rb":
                self._analyze_ruby(file_path, content)

        return self._models

    # ==================== Java / JPA / Hibernate ====================

    def _analyze_java(self, file_path: Path, content: str) -> None:
        """检测 JPA / Hibernate 实体。"""
        # 检测 @Entity 注解
        for entity_m in re.finditer(r"@Entity\b", content):
            table_name = self._extract_class_name(content, entity_m.start())
            rel_path = self._relative(file_path)

            # 提取 @Table 注解
            table_m = re.search(r"@Table\s*\(\s*name\s*=\s*\"(\w+)\"", content[entity_m.start():entity_m.start() + 200])
            if table_m:
                table_name = table_name or table_m.group(1)

            if not table_name:
                continue

            model = DbModel(table_name=table_name, class_name=table_name,
                            file_path=rel_path, line=self._line_of(content, entity_m.start()),
                            orm="JPA/Hibernate")

            # 提取字段
            self._extract_java_fields(content, entity_m.start(), model)
            self._models.append(model)

    def _extract_java_fields(self, content: str, start: int, model: DbModel) -> None:
        """提取 Java 实体字段。"""
        # 找到类体结束
        class_body = self._find_class_body(content, start)
        if not class_body:
            return

        # 字段声明: private Type fieldName;
        field_pattern = re.compile(
            r'@(?:Id|GeneratedValue|Column|ManyToOne|OneToMany|ManyToMany|OneToOne|'
            r'JoinColumn|Enumerated|Lob|Transient|NotNull|JsonIgnore|CreatedDate|'
            r'LastModifiedDate)\s*\n[^;]*?'
            r'private\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]',
            re.DOTALL
        )

        for fm in field_pattern.finditer(class_body):
            java_type = fm.group(1)
            field_name = fm.group(2)
            is_primary = "@Id" in class_body[fm.start():fm.start() + fm.span()[1] - fm.span()[0]]

            # 关系检测
            is_relation = False
            relation_type = ""
            relation_target = ""
            if "ManyToOne" in class_body[max(0, fm.start() - 200):fm.start()]:
                is_relation = True
                relation_type = "ManyToOne"
                relation_target = java_type
            elif "OneToMany" in class_body[max(0, fm.start() - 200):fm.start()]:
                is_relation = True
                relation_type = "OneToMany"
                relation_target = java_type.replace("List<", "").replace("Set<", "").rstrip(">")
            elif "ManyToMany" in class_body[max(0, fm.start() - 200):fm.start()]:
                is_relation = True
                relation_type = "ManyToMany"
                relation_target = java_type.replace("List<", "").replace("Set<", "").rstrip(">")
            elif "OneToOne" in class_body[max(0, fm.start() - 200):fm.start()]:
                is_relation = True
                relation_type = "OneToOne"
                relation_target = java_type

            # 提取 @Column 信息
            nullable = True
            max_length = 0
            col_match = re.search(r"@Column\s*\(([^)]+)\)", class_body[max(0, fm.start() - 200):fm.start()])
            if col_match:
                col_def = col_match.group(1)
                if "nullable = false" in col_def:
                    nullable = False
                length_m = re.search(r"length\s*=\s*(\d+)", col_def)
                if length_m:
                    max_length = int(length_m.group(1))

            sql_type = self.JAVA_TYPE_MAP.get(java_type, java_type.upper())

            model.fields.append(DbField(
                name=field_name, field_type=sql_type, nullable=nullable,
                primary_key=is_primary, max_length=max_length,
                is_relation=is_relation, relation_type=relation_type,
                relation_target=relation_target,
            ))

    # ==================== Python ====================

    def _analyze_python(self, file_path: Path, content: str) -> None:
        """检测 Django Model / SQLAlchemy Model。"""
        # Django Model
        for m in re.finditer(r"class\s+(\w+)\s*\(\s*models\.Model\s*\)", content):
            class_name = m.group(1)
            table_name = self._to_snake_case(class_name)

            # 提取 Meta.table_name
            meta_m = re.search(r"class\s+Meta\s*:.*?db_table\s*=\s*['\"](\w+)['\"]", content[m.start():], re.DOTALL)
            if meta_m:
                table_name = meta_m.group(1)

            model = DbModel(table_name=table_name, class_name=class_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="Django ORM")

            # 提取字段
            self._extract_django_fields(content, m.start(), model)
            self._models.append(model)

        # SQLAlchemy Model
        for m in re.finditer(r"class\s+(\w+)\s*\(\s*(?:Base|db\.Model|DeclarativeBase)\s*\)", content):
            class_name = m.group(1)
            table_name = self._to_snake_case(class_name)

            # __tablename__
            tn_m = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", content[m.start():m.start() + 500])
            if tn_m:
                table_name = tn_m.group(1)

            model = DbModel(table_name=table_name, class_name=class_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="SQLAlchemy")

            self._extract_sqlalchemy_fields(content, m.start(), model)
            self._models.append(model)

    def _extract_django_fields(self, content: str, start: int, model: DbModel) -> None:
        body = self._find_python_class_body(content, start)
        if not body:
            return

        # 字段: name = models.CharField(max_length=100, null=True)
        field_pattern = re.compile(
            r'(\w+)\s*=\s*models\.(\w+)\s*\(([^)]*)\)',
            re.DOTALL
        )
        for fm in field_pattern.finditer(body):
            field_name = fm.group(1)
            field_type = fm.group(2)
            field_args = fm.group(3)

            is_primary = field_type in ("AutoField", "BigAutoField")
            nullable = "null=True" not in field_args
            max_length = 0
            default_value = ""

            # ForeignKey
            is_relation = field_type == "ForeignKey"
            relation_target = ""
            if is_relation:
                relation_m = re.search(r"ForeignKey\s*\(\s*['\"]?(\w+)['\"]?", field_args)
                if relation_m:
                    relation_target = relation_m.group(1)

            # max_length
            len_m = re.search(r"max_length\s*=\s*(\d+)", field_args)
            if len_m:
                max_length = int(len_m.group(1))

            # default
            def_m = re.search(r"default\s*=\s*([^,)]+)", field_args)
            if def_m:
                default_value = def_m.group(1).strip()

            model.fields.append(DbField(
                name=field_name, field_type=field_type,
                nullable=nullable, primary_key=is_primary,
                max_length=max_length, default_value=default_value,
                is_relation=is_relation, relation_type="ForeignKey" if is_relation else "",
                relation_target=relation_target,
            ))

    def _extract_sqlalchemy_fields(self, content: str, start: int, model: DbModel) -> None:
        body = self._find_python_class_body(content, start)
        if not body:
            return

        # Column(Integer, primary_key=True)
        for fm in re.finditer(r"(\w+)\s*=\s*Column\s*\(([^)]+)\)", body, re.DOTALL):
            field_name = fm.group(1)
            args = fm.group(2)

            col_type = "VARCHAR"
            type_m = re.search(r"(\w+)", args)
            if type_m:
                col_type = type_m.group(1)

            is_primary = "primary_key=True" in args
            nullable = "nullable=False" not in args
            default_value = ""
            def_m = re.search(r"default\s*=\s*([^,)]+)", args)
            if def_m:
                default_value = def_m.group(1).strip()

            model.fields.append(DbField(
                name=field_name, field_type=col_type,
                nullable=nullable, primary_key=is_primary,
                default_value=default_value,
            ))

        # relationship()
        for fm in re.finditer(r"(\w+)\s*=\s*relationship\s*\(\s*['\"]?(\w+)['\"]?", body):
            model.fields.append(DbField(
                name=fm.group(1), field_type="relationship",
                is_relation=True, relation_type="relationship",
                relation_target=fm.group(2),
            ))

    # ==================== TypeScript / TypeORM / Prisma ====================

    def _analyze_typescript(self, file_path: Path, content: str) -> None:
        """检测 TypeORM / Prisma 模型。"""
        # TypeORM Entity
        for m in re.finditer(r"@Entity\s*\(\s*\{?\s*(?:name\s*:\s*['\"](\w+)['\"])?", content):
            table_name = m.group(1)
            class_name = self._extract_class_name(content, m.start())
            if not table_name:
                table_name = class_name.lower() if class_name else "entity"

            model = DbModel(table_name=table_name, class_name=table_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="TypeORM")

            self._extract_typeorm_fields(content, m.start(), model)
            self._models.append(model)

    def _extract_typeorm_fields(self, content: str, start: int, model: DbModel) -> None:
        # @Column() / @PrimaryColumn() / @PrimaryGeneratedColumn()
        for fm in re.finditer(
            r"@(?:PrimaryGeneratedColumn|PrimaryColumn|Column)\s*\([^)]*\)\s*\n\s*(\w+)\s*:\s*(\w+)",
            content[start:start + 2000]
        ):
            field_name = fm.group(1)
            ts_type = fm.group(2)
            sql_type = {"string": "VARCHAR", "number": "INTEGER", "boolean": "BOOLEAN",
                        "Date": "TIMESTAMP", "text": "TEXT"}.get(ts_type.lower(), ts_type.upper())
            is_primary = "Primary" in fm.group(0)

            model.fields.append(DbField(
                name=field_name, field_type=sql_type, primary_key=is_primary,
            ))

        # @ManyToOne, @OneToMany etc.
        for fm in re.finditer(
            r"@(ManyToOne|OneToMany|ManyToMany|OneToOne)\s*\(\s*\(\)\s*=>\s*(\w+)",
            content[start:start + 2000]
        ):
            model.fields.append(DbField(
                name=fm.group(2).lower(), field_type=fm.group(1),
                is_relation=True, relation_type=fm.group(1),
                relation_target=fm.group(2),
            ))

    def _analyze_javascript(self, file_path: Path, content: str) -> None:
        """检测 Sequelize / Mongoose 模型。"""
        # Sequelize: sequelize.define('User', { ... })
        for m in re.finditer(r"\.define\s*\(\s*['\"](\w+)['\"]", content):
            table_name = m.group(1)
            model = DbModel(table_name=table_name, class_name=table_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="Sequelize")

            # 提取字段
            field_block = content[m.start():m.start() + 2000]
            for fm in re.finditer(r"(\w+)\s*:\s*\{\s*type\s*:\s*(\w+)\.(\w+)", field_block):
                field_name = fm.group(1)
                sql_type = fm.group(3).upper()
                model.fields.append(DbField(name=field_name, field_type=sql_type))

            self._models.append(model)

        # Mongoose: new Schema({ ... })
        for m in re.finditer(r"new\s+(?:mongoose\.)?Schema\s*\(\s*\{", content):
            class_name = self._extract_class_name_or_var(content, m.start())
            table_name = class_name.lower() if class_name else "collection"

            model = DbModel(table_name=table_name, class_name=class_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="Mongoose")

            field_block = content[m.start():m.start() + 3000]
            for fm in re.finditer(r"(\w+)\s*:\s*\{\s*type\s*:\s*(\w+)", field_block):
                sql_type = fm.group(2).upper()
                model.fields.append(DbField(name=fm.group(1), field_type=sql_type))

            self._models.append(model)

    # ==================== Go / GORM ====================

    def _analyze_go(self, file_path: Path, content: str) -> None:
        for m in re.finditer(r"type\s+(\w+)\s+struct\s*\{", content):
            class_name = m.group(1)
            table_name = self._to_snake_case(class_name)

            # 检查是否为 GORM 模型
            body = content[m.start():m.start() + 2000]
            if "gorm.Model" not in body and "gorm:" not in body:
                continue

            model = DbModel(table_name=table_name, class_name=class_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="GORM")

            # 提取字段: Name string `gorm:"column:name;type:varchar(100)"`
            for fm in re.finditer(r"(\w+)\s+(\w+(?:\.\w+)?)\s+(?:`gorm:\"([^\"]+)\"`)?", body):
                field_name = fm.group(1)
                go_type = fm.group(2)
                gorm_tag = fm.group(3) or ""

                go_to_sql = {"string": "VARCHAR", "int": "INTEGER", "int64": "BIGINT",
                             "float64": "DOUBLE", "bool": "BOOLEAN", "time.Time": "TIMESTAMP",
                             "decimal.Decimal": "DECIMAL", "[]byte": "BLOB"}

                sql_type = go_to_sql.get(go_type, go_type.upper())
                is_primary = "primaryKey" in gorm_tag
                nullable = "not null" not in gorm_tag.lower()

                model.fields.append(DbField(
                    name=field_name, field_type=sql_type,
                    nullable=nullable, primary_key=is_primary,
                ))

            self._models.append(model)

    # ==================== PHP / Laravel Eloquent ====================

    def _analyze_php(self, file_path: Path, content: str) -> None:
        for m in re.finditer(r"class\s+(\w+)\s+extends\s+Model", content):
            class_name = m.group(1)
            table_name = self._to_snake_case(class_name).replace("_", "")

            # 检查 $table
            table_m = re.search(r"\$table\s*=\s*['\"](\w+)['\"]", content[m.start():m.start() + 500])
            if table_m:
                table_name = table_m.group(1)

            model = DbModel(table_name=table_name, class_name=class_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="Eloquent")

            # $fillable / $casts
            fillable_m = re.search(r"\$fillable\s*=\s*\[([^\]]+)\]", content[m.start():m.start() + 500])
            if fillable_m:
                fields_str = fillable_m.group(1)
                for field_name in re.findall(r"['\"](\w+)['\"]", fields_str):
                    model.fields.append(DbField(name=field_name, field_type="VARCHAR"))

            self._models.append(model)

    # ==================== Ruby / ActiveRecord ====================

    def _analyze_ruby(self, file_path: Path, content: str) -> None:
        for m in re.finditer(r"class\s+(\w+)\s*<\s*ApplicationRecord", content):
            class_name = m.group(1)
            table_name = self._to_snake_case(class_name).replace("_", "")

            model = DbModel(table_name=table_name, class_name=class_name,
                            file_path=self._relative(file_path),
                            line=self._line_of(content, m.start()), orm="ActiveRecord")

            self._models.append(model)

    # ==================== Helpers ====================

    def _relative(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(self._root)).replace("\\", "/")
        except ValueError:
            return str(file_path)

    @staticmethod
    def _extract_class_name(content: str, pos: int) -> str:
        chunk = content[pos:pos + 200]
        m = re.search(r"class\s+(\w+)", chunk)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_class_name_or_var(content: str, pos: int) -> str:
        # const User = mongoose.model('User', ...)
        chunk = content[max(0, pos - 200):pos]
        m = re.search(r"(\w+)\s*=\s*(?:new\s+)?(?:mongoose\.)?Schema", chunk)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _find_class_body(content: str, start: int) -> str:
        """找到类体（从 { 到匹配的 }）。"""
        brace_start = content.find("{", start)
        if brace_start == -1:
            return ""
        depth = 0
        for i in range(brace_start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    return content[brace_start:i + 1]
        return ""

    @staticmethod
    def _find_python_class_body(content: str, start: int) -> str:
        """找到 Python 类体（基于缩进）。"""
        lines = content[start:].split("\n")
        if len(lines) < 2:
            return ""
        result = [lines[0]]
        class_indent = len(lines[0]) - len(lines[0].lstrip())
        for line in lines[1:]:
            stripped = line.lstrip()
            if stripped == "":
                result.append(line)
                continue
            current_indent = len(line) - len(stripped)
            if current_indent <= class_indent and stripped:
                break
            result.append(line)
        return "\n".join(result)

    @staticmethod
    def _to_snake_case(name: str) -> str:
        result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        result = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", result)
        return result.lower()

    @staticmethod
    def _line_of(content: str, pos: int) -> int:
        return content[:pos].count("\n") + 1


def build_models_summary(models: list[DbModel]) -> dict[str, Any]:
    return {
        "total_tables": len(models),
        "total_fields": sum(len(m.fields) for m in models),
        "by_orm": list(set(m.orm for m in models)),
        "models": [m.to_dict() for m in models],
    }