"""
项目类型检测器：识别项目类型、技术栈、架构模式、入口点。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ProjectInfo:
    """项目信息容器。"""

    def __init__(self):
        self.project_type: str = "unknown"
        self.project_subtype: str = ""
        self.display_name: str = ""
        self.description: str = ""
        self.version: str = ""
        self.language: str = ""
        self.frameworks: list[str] = []
        self.build_tools: list[str] = []
        self.databases: list[str] = []
        self.architecture: str = "unknown"
        self.entry_points: list[str] = []
        self.build_files: list[str] = []
        self.tech_stack: dict[str, list[str]] = {}

    def to_dict(self) -> dict:
        return {
            "project_type": self.project_type,
            "project_subtype": self.project_subtype,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "language": self.language,
            "frameworks": self.frameworks,
            "build_tools": self.build_tools,
            "databases": self.databases,
            "architecture": self.architecture,
            "entry_points": self.entry_points,
            "build_files": self.build_files,
            "tech_stack": self.tech_stack,
        }


class ProjectDetector:
    """检测项目类型、技术栈、架构模式。"""

    # 构建文件 → (项目类型, 构建工具, 语言)
    BUILD_FILE_MAP = {
        "pom.xml": ("java", "Maven", "java"),
        "build.gradle": ("java", "Gradle", "java"),
        "build.gradle.kts": ("java", "Gradle Kotlin", "kotlin"),
        "package.json": ("node", "npm/yarn/pnpm", "javascript"),
        "composer.json": ("php", "Composer", "php"),
        "requirements.txt": ("python", "pip", "python"),
        "setup.py": ("python", "setuptools", "python"),
        "setup.cfg": ("python", "setuptools", "python"),
        "pyproject.toml": ("python", "pip/poetry", "python"),
        "Pipfile": ("python", "pipenv", "python"),
        "Cargo.toml": ("rust", "Cargo", "rust"),
        "go.mod": ("go", "Go Modules", "go"),
        "CMakeLists.txt": ("cpp", "CMake", "cpp"),
        "Makefile": ("generic", "Make", "c"),
        "Gemfile": ("ruby", "Bundler", "ruby"),
        "Rakefile": ("ruby", "Rake", "ruby"),
        "build.sbt": ("scala", "SBT", "scala"),
        "mix.exs": ("elixir", "Mix", "elixir"),
        "rebar.config": ("erlang", "Rebar", "erlang"),
        "project.clj": ("clojure", "Leiningen", "clojure"),
        "Package.swift": ("swift", "SwiftPM", "swift"),
        "pubspec.yaml": ("dart", "pub", "dart"),
        "stack.yaml": ("haskell", "Stack", "haskell"),
        "cabal.project": ("haskell", "Cabal", "haskell"),
        "build.zig": ("zig", "Zig Build", "zig"),
        "Makefile.PL": ("perl", "EUMM", "perl"),
        "angular.json": ("angular", "Angular CLI", "typescript"),
        "next.config.js": ("nextjs", "Next.js", "typescript"),
        "next.config.mjs": ("nextjs", "Next.js", "typescript"),
        "next.config.ts": ("nextjs", "Next.js", "typescript"),
        "nuxt.config.js": ("nuxt", "Nuxt.js", "typescript"),
        "nuxt.config.ts": ("nuxt", "Nuxt.js", "typescript"),
        "svelte.config.js": ("svelte", "SvelteKit", "typescript"),
        "vite.config.js": ("vite", "Vite", "javascript"),
        "vite.config.ts": ("vite", "Vite", "typescript"),
        "webpack.config.js": ("webpack", "Webpack", "javascript"),
        "rollup.config.js": ("rollup", "Rollup", "javascript"),
        "tsconfig.json": ("typescript", "TypeScript", "typescript"),
        "Dockerfile": ("docker", "Docker", "generic"),
        "docker-compose.yml": ("docker", "Docker Compose", "generic"),
        "docker-compose.yaml": ("docker", "Docker Compose", "generic"),
        ".drone.yml": ("ci", "Drone CI", "generic"),
        ".github/workflows": ("ci", "GitHub Actions", "generic"),
        ".gitlab-ci.yml": ("ci", "GitLab CI", "generic"),
        "Jenkinsfile": ("ci", "Jenkins", "generic"),
        "artisan": ("laravel", "Artisan", "php"),
        "symfony.lock": ("symfony", "Symfony", "php"),
        "manage.py": ("django", "Django", "python"),
        "alembic.ini": ("python", "Alembic", "python"),
        "migrations": ("python", "Alembic/Django", "python"),
        "ormconfig.json": ("node", "TypeORM", "typescript"),
        "prisma": ("node", "Prisma", "typescript"),
        "drizzle.config.ts": ("node", "Drizzle", "typescript"),
        ".eslintrc.js": ("node", "ESLint", "javascript"),
        ".eslintrc.json": ("node", "ESLint", "javascript"),
        ".eslintrc.yaml": ("node", "ESLint", "javascript"),
        ".prettierrc": ("node", "Prettier", "javascript"),
        "tailwind.config.js": ("node", "Tailwind CSS", "javascript"),
        "tailwind.config.ts": ("node", "Tailwind CSS", "typescript"),
        "postcss.config.js": ("node", "PostCSS", "javascript"),
        "babel.config.js": ("node", "Babel", "javascript"),
        ".babelrc": ("node", "Babel", "javascript"),
        "jest.config.js": ("node", "Jest", "javascript"),
        "jest.config.ts": ("node", "Jest", "typescript"),
        "vitest.config.ts": ("node", "Vitest", "typescript"),
        "playwright.config.ts": ("node", "Playwright", "typescript"),
        "cypress.config.js": ("node", "Cypress", "javascript"),
        "cypress.config.ts": ("node", "Cypress", "typescript"),
        "nginx.conf": ("infra", "Nginx", "generic"),
        "nginx": ("infra", "Nginx", "generic"),
        "k8s": ("infra", "Kubernetes", "generic"),
        "kubernetes": ("infra", "Kubernetes", "generic"),
        "helm": ("infra", "Helm", "generic"),
        "terraform": ("infra", "Terraform", "generic"),
        "ansible": ("infra", "Ansible", "generic"),
        "Vagrantfile": ("infra", "Vagrant", "generic"),
    }

    # 框架特征 → 基于构建文件内容的关键词
    FRAMEWORK_PATTERNS = {
        "pom.xml": {
            "spring-boot": ("Spring Boot", "java"),
            "spring-cloud": ("Spring Cloud", "java"),
            "spring-security": ("Spring Security", "java"),
            "mybatis": ("MyBatis", "java"),
            "mybatis-plus": ("MyBatis Plus", "java"),
            "hibernate": ("Hibernate", "java"),
            "junit": ("JUnit", "java"),
            "log4j": ("Log4j", "java"),
            "slf4j": ("SLF4J", "java"),
            "lombok": ("Lombok", "java"),
            "thymeleaf": ("Thymeleaf", "java"),
            "freemarker": ("FreeMarker", "java"),
        },
        "build.gradle": {
            "spring-boot": ("Spring Boot", "java"),
            "spring-cloud": ("Spring Cloud", "java"),
            "ktor": ("Ktor", "kotlin"),
            "kotlin": ("Kotlin", "kotlin"),
            "android": ("Android", "java"),
        },
        "package.json": {
            "react": ("React", "javascript"),
            "react-dom": ("React", "javascript"),
            "next": ("Next.js", "typescript"),
            "vue": ("Vue.js", "javascript"),
            "@vue": ("Vue.js", "javascript"),
            "nuxt": ("Nuxt.js", "typescript"),
            "angular": ("Angular", "typescript"),
            "@angular/core": ("Angular", "typescript"),
            "svelte": ("Svelte", "typescript"),
            "express": ("Express", "javascript"),
            "koa": ("Koa", "javascript"),
            "fastify": ("Fastify", "javascript"),
            "nestjs": ("NestJS", "typescript"),
            "@nestjs/core": ("NestJS", "typescript"),
            "electron": ("Electron", "javascript"),
            "react-native": ("React Native", "javascript"),
            "expo": ("Expo", "javascript"),
            "tailwindcss": ("Tailwind CSS", "javascript"),
            "bootstrap": ("Bootstrap", "javascript"),
            "sass": ("Sass", "javascript"),
            "typescript": ("TypeScript", "typescript"),
            "jest": ("Jest", "javascript"),
            "vitest": ("Vitest", "typescript"),
            "mocha": ("Mocha", "javascript"),
            "cypress": ("Cypress", "javascript"),
            "playwright": ("Playwright", "typescript"),
            "eslint": ("ESLint", "javascript"),
            "prettier": ("Prettier", "javascript"),
            "axios": ("Axios", "javascript"),
            "lodash": ("Lodash", "javascript"),
            "moment": ("Moment.js", "javascript"),
            "dayjs": ("Day.js", "javascript"),
            "redux": ("Redux", "javascript"),
            "zustand": ("Zustand", "javascript"),
            "pinia": ("Pinia", "javascript"),
            "vuex": ("Vuex", "javascript"),
            "mobx": ("MobX", "javascript"),
            "graphql": ("GraphQL", "javascript"),
            "apollo": ("Apollo", "javascript"),
            "trpc": ("tRPC", "typescript"),
            "mui": ("Material UI", "javascript"),
            "antd": ("Ant Design", "javascript"),
            "chakra": ("Chakra UI", "javascript"),
            "vite": ("Vite", "javascript"),
            "webpack": ("Webpack", "javascript"),
            "rollup": ("Rollup", "javascript"),
            "esbuild": ("esbuild", "javascript"),
            "prisma": ("Prisma", "typescript"),
            "drizzle": ("Drizzle ORM", "typescript"),
            "typeorm": ("TypeORM", "typescript"),
            "sequelize": ("Sequelize", "javascript"),
            "mongoose": ("Mongoose", "javascript"),
            "mysql2": ("MySQL", "javascript"),
            "pg": ("PostgreSQL", "javascript"),
            "redis": ("Redis", "javascript"),
            "ioredis": ("Redis", "javascript"),
            "socket.io": ("Socket.IO", "javascript"),
            "ws": ("WebSocket", "javascript"),
            "three": ("Three.js", "javascript"),
            "d3": ("D3.js", "javascript"),
            "echarts": ("ECharts", "javascript"),
            "chart.js": ("Chart.js", "javascript"),
            "swr": ("SWR", "javascript"),
            "react-query": ("React Query", "javascript"),
            "tanstack": ("TanStack", "javascript"),
            "zustand": ("Zustand", "javascript"),
            "jotai": ("Jotai", "javascript"),
            "recoil": ("Recoil", "javascript"),
            "formik": ("Formik", "javascript"),
            "react-hook-form": ("React Hook Form", "javascript"),
            "yup": ("Yup", "javascript"),
            "zod": ("Zod", "typescript"),
        },
        "composer.json": {
            "laravel": ("Laravel", "php"),
            "symfony": ("Symfony", "php"),
            "slim": ("Slim", "php"),
            "laminas": ("Laminas", "php"),
            "yii": ("Yii", "php"),
            "cakephp": ("CakePHP", "php"),
            "codeigniter": ("CodeIgniter", "php"),
            "thinkphp": ("ThinkPHP", "php"),
            "phpunit": ("PHPUnit", "php"),
            "monolog": ("Monolog", "php"),
            "guzzlehttp": ("Guzzle", "php"),
            "doctrine": ("Doctrine", "php"),
            "eloquent": ("Eloquent", "php"),
            "twig": ("Twig", "php"),
            "blade": ("Blade", "php"),
            "redis": ("Redis", "php"),
            "predis": ("Predis", "php"),
            "swagger": ("Swagger", "php"),
            "phpstan": ("PHPStan", "php"),
            "php-cs-fixer": ("PHP CS Fixer", "php"),
        },
        "requirements.txt": {
            "django": ("Django", "python"),
            "flask": ("Flask", "python"),
            "fastapi": ("FastAPI", "python"),
            "tornado": ("Tornado", "python"),
            "aiohttp": ("aiohttp", "python"),
            "sanic": ("Sanic", "python"),
            "pyramid": ("Pyramid", "python"),
            "sqlalchemy": ("SQLAlchemy", "python"),
            "pydantic": ("Pydantic", "python"),
            "pytest": ("pytest", "python"),
            "unittest": ("unittest", "python"),
            "celery": ("Celery", "python"),
            "redis": ("Redis", "python"),
            "pymongo": ("MongoDB", "python"),
            "psycopg2": ("PostgreSQL", "python"),
            "mysqlclient": ("MySQL", "python"),
            "requests": ("Requests", "python"),
            "httpx": ("HTTPX", "python"),
            "beautifulsoup4": ("BeautifulSoup", "python"),
            "scrapy": ("Scrapy", "python"),
            "numpy": ("NumPy", "python"),
            "pandas": ("Pandas", "python"),
            "matplotlib": ("Matplotlib", "python"),
            "plotly": ("Plotly", "python"),
            "scikit-learn": ("scikit-learn", "python"),
            "tensorflow": ("TensorFlow", "python"),
            "torch": ("PyTorch", "python"),
            "transformers": ("Transformers", "python"),
            "opencv": ("OpenCV", "python"),
            "pillow": ("Pillow", "python"),
            "jinja2": ("Jinja2", "python"),
            "click": ("Click", "python"),
            "typer": ("Typer", "python"),
            "rich": ("Rich", "python"),
            "loguru": ("Loguru", "python"),
            "pydantic-settings": ("Pydantic Settings", "python"),
            "alembic": ("Alembic", "python"),
            "gunicorn": ("Gunicorn", "python"),
            "uvicorn": ("Uvicorn", "python"),
            "websockets": ("WebSockets", "python"),
            "django-rest-framework": ("Django REST", "python"),
            "djangorestframework": ("Django REST", "python"),
            "django-ninja": ("Django Ninja", "python"),
            "drf-spectacular": ("DRF Spectacular", "python"),
            "langchain": ("LangChain", "python"),
            "llama-index": ("LlamaIndex", "python"),
            "openai": ("OpenAI", "python"),
            "chromadb": ("ChromaDB", "python"),
        },
        "pyproject.toml": {
            "django": ("Django", "python"),
            "flask": ("Flask", "python"),
            "fastapi": ("FastAPI", "python"),
            "litestar": ("Litestar", "python"),
            "poetry": ("Poetry", "python"),
            "hatch": ("Hatch", "python"),
            "pdm": ("PDM", "python"),
            "black": ("Black", "python"),
            "ruff": ("Ruff", "python"),
            "mypy": ("mypy", "python"),
            "isort": ("isort", "python"),
            "pytest": ("pytest", "python"),
            "tox": ("tox", "python"),
            "pre-commit": ("pre-commit", "python"),
            "mkdocs": ("MkDocs", "python"),
            "sphinx": ("Sphinx", "python"),
        },
        "go.mod": {
            "gin-gonic": ("Gin", "go"),
            "gin-contrib": ("Gin", "go"),
            "echo": ("Echo", "go"),
            "fiber": ("Fiber", "go"),
            "chi": ("Chi", "go"),
            "gorilla/mux": ("Gorilla Mux", "go"),
            "gorilla/websocket": ("Gorilla WebSocket", "go"),
            "gorm": ("GORM", "go"),
            "sqlx": ("sqlx", "go"),
            "pgx": ("pgx", "go"),
            "redis": ("Redis", "go"),
            "mongo-driver": ("MongoDB", "go"),
            "zap": ("Zap", "go"),
            "logrus": ("Logrus", "go"),
            "zerolog": ("Zerolog", "go"),
            "viper": ("Viper", "go"),
            "cobra": ("Cobra", "go"),
            "grpc": ("gRPC", "go"),
            "protobuf": ("Protobuf", "go"),
            "kratos": ("Kratos", "go"),
            "go-zero": ("go-zero", "go"),
            "go-kit": ("Go Kit", "go"),
            "go-micro": ("Go Micro", "go"),
            "wire": ("Wire", "go"),
            "testify": ("Testify", "go"),
            "ginkgo": ("Ginkgo", "go"),
            "prometheus": ("Prometheus", "go"),
            "jaeger": ("Jaeger", "go"),
            "opentelemetry": ("OpenTelemetry", "go"),
            "ent": ("Ent", "go"),
            "bun": ("Bun", "go"),
            "sqlc": ("sqlc", "go"),
            "swaggo": ("Swaggo", "go"),
        },
        "Cargo.toml": {
            "actix-web": ("Actix Web", "rust"),
            "actix-rt": ("Actix", "rust"),
            "rocket": ("Rocket", "rust"),
            "axum": ("Axum", "rust"),
            "warp": ("Warp", "rust"),
            "tide": ("Tide", "rust"),
            "tokio": ("Tokio", "rust"),
            "async-std": ("async-std", "rust"),
            "serde": ("Serde", "rust"),
            "serde_json": ("Serde JSON", "rust"),
            "diesel": ("Diesel", "rust"),
            "sqlx": ("sqlx", "rust"),
            "rusqlite": ("Rusqlite", "rust"),
            "redis": ("Redis", "rust"),
            "mongodb": ("MongoDB", "rust"),
            "reqwest": ("Reqwest", "rust"),
            "hyper": ("Hyper", "rust"),
            "tonic": ("Tonic", "rust"),
            "prost": ("Prost", "rust"),
            "clap": ("Clap", "rust"),
            "structopt": ("StructOpt", "rust"),
            "tracing": ("Tracing", "rust"),
            "log": ("Log", "rust"),
            "env_logger": ("env_logger", "rust"),
            "thiserror": ("thiserror", "rust"),
            "anyhow": ("Anyhow", "rust"),
            "rayon": ("Rayon", "rust"),
            "wasm-bindgen": ("WASM", "rust"),
            "yew": ("Yew", "rust"),
            "leptos": ("Leptos", "rust"),
            "tauri": ("Tauri", "rust"),
            "bevy": ("Bevy", "rust"),
            "egui": ("egui", "rust"),
            "iced": ("Iced", "rust"),
            "ratatui": ("Ratatui", "rust"),
        },
        "Gemfile": {
            "rails": ("Ruby on Rails", "ruby"),
            "sinatra": ("Sinatra", "ruby"),
            "rspec": ("RSpec", "ruby"),
            "capybara": ("Capybara", "ruby"),
            "devise": ("Devise", "ruby"),
            "puma": ("Puma", "ruby"),
            "sidekiq": ("Sidekiq", "ruby"),
            "pg": ("PostgreSQL", "ruby"),
            "mysql2": ("MySQL", "ruby"),
            "redis": ("Redis", "ruby"),
            "mongoid": ("MongoDB", "ruby"),
            "active-record": ("ActiveRecord", "ruby"),
            "graphql": ("GraphQL", "ruby"),
            "rspec-rails": ("RSpec Rails", "ruby"),
            "factory_bot": ("Factory Bot", "ruby"),
            "rubocop": ("RuboCop", "ruby"),
        },
    }

    # 数据库检测关键词
    DB_PATTERNS = {
        "mysql": "MySQL", "mysqli": "MySQL", "pdo_mysql": "MySQL",
        "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "pgsql": "PostgreSQL", "pdo_pgsql": "PostgreSQL",
        "sqlite": "SQLite", "sqlite3": "SQLite",
        "mongodb": "MongoDB", "mongo": "MongoDB",
        "redis": "Redis",
        "mariadb": "MariaDB", "mariadb": "MariaDB",
        "oracle": "Oracle",
        "mssql": "SQL Server", "sqlserver": "SQL Server",
        "elasticsearch": "Elasticsearch",
        "cassandra": "Cassandra",
        "neo4j": "Neo4j",
        "dynamodb": "DynamoDB",
        "couchdb": "CouchDB",
        "firebase": "Firebase",
        "supabase": "Supabase",
        "clickhouse": "ClickHouse",
        "timescaledb": "TimescaleDB",
        "cockroachdb": "CockroachDB",
        "tidb": "TiDB",
        "oceanbase": "OceanBase",
        "h2": "H2",
        "h2database": "H2",
    }

    # 架构模式目录特征
    ARCHITECTURE_PATTERNS = {
        "mvc": {
            "dirs": ["controller", "model", "view", "controllers", "models", "views"],
            "name": "MVC (Model-View-Controller)",
        },
        "ddd": {
            "dirs": ["domain", "application", "infrastructure", "interfaces", "entity", "repository", "service", "valueobject"],
            "name": "DDD (领域驱动设计)",
        },
        "clean": {
            "dirs": ["entities", "usecases", "interfaces", "frameworks", "use_cases", "interface_adapters"],
            "name": "Clean Architecture",
        },
        "hexagonal": {
            "dirs": ["ports", "adapters", "domain", "application", "infrastructure", "primary", "secondary"],
            "name": "Hexagonal Architecture (端口适配器)",
        },
        "layered": {
            "dirs": ["controller", "service", "repository", "dao", "mapper", "entity", "dto", "vo"],
            "name": "分层架构",
        },
        "microservices": {
            "dirs": ["gateway", "discovery", "config-server", "auth-service", "user-service", "order-service"],
            "name": "微服务架构",
        },
        "modular_monolith": {
            "dirs": ["modules", "module", "bounded_context", "context"],
            "name": "模块化单体架构",
        },
        "cqrs": {
            "dirs": ["commands", "queries", "events", "command", "query", "event", "projection", "aggregate"],
            "name": "CQRS (命令查询职责分离)",
        },
        "event_driven": {
            "dirs": ["events", "handlers", "listeners", "publishers", "subscribers", "consumers", "producers"],
            "name": "事件驱动架构",
        },
    }

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._info = ProjectInfo()

    def detect(self) -> ProjectInfo:
        """执行全面检测，返回项目信息。"""
        self._detect_build_files()
        self._detect_frameworks()
        self._detect_databases()
        self._detect_architecture()
        self._detect_entry_points()
        self._determine_project_type()
        self._build_tech_stack()
        return self._info

    def _detect_build_files(self) -> None:
        """扫描项目根目录及一级子目录，识别构建文件。"""
        search_dirs = [self._root] + [d for d in self._root.iterdir() if d.is_dir()]

        for search_dir in search_dirs:
            for entry in search_dir.iterdir():
                if not entry.is_file():
                    continue
                name = entry.name
                if name in self.BUILD_FILE_MAP:
                    proj_type, build_tool, lang = self.BUILD_FILE_MAP[name]
                    self._info.build_files.append(name)
                    if build_tool not in self._info.build_tools:
                        self._info.build_tools.append(build_tool)
                    if not self._info.language:
                        self._info.language = lang
                    if not self._info.project_type or self._info.project_type == "unknown":
                        self._info.project_type = proj_type

                    # 解析构建文件获取元数据
                    self._parse_build_file(entry, name)

    def _parse_build_file(self, path: Path, name: str) -> None:
        """解析构建文件，提取名称、版本、描述。"""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        # package.json
        if name == "package.json":
            try:
                data = json.loads(content)
                self._info.display_name = data.get("name", "")
                self._info.version = data.get("version", "")
                self._info.description = data.get("description", "")
            except json.JSONDecodeError:
                pass

        # pom.xml
        elif name == "pom.xml":
            for tag, field in [("<name>", "display_name"), ("<description>", "description"), ("<version>", "version")]:
                m = re.search(rf"{tag}(.*?)</?\w+>", content)
                if m and not getattr(self._info, field):
                    setattr(self._info, field, m.group(1).strip())

        # composer.json
        elif name == "composer.json":
            try:
                data = json.loads(content)
                self._info.display_name = data.get("name", "")
                self._info.description = data.get("description", "")
            except json.JSONDecodeError:
                pass

        # pyproject.toml
        elif name == "pyproject.toml":
            for field, pattern in [("display_name", r'name\s*=\s*"([^"]*)"'), ("version", r'version\s*=\s*"([^"]*)"'), ("description", r'description\s*=\s*"([^"]*)"')]:
                m = re.search(pattern, content)
                if m and not getattr(self._info, field):
                    setattr(self._info, field, m.group(1))

        # setup.py
        elif name == "setup.py":
            for field, pattern in [("display_name", r'name\s*=\s*["\']([^"\']+)'), ("version", r'version\s*=\s*["\']([^"\']+)'), ("description", r'description\s*=\s*["\']([^"\']+)')]:
                m = re.search(pattern, content)
                if m and not getattr(self._info, field):
                    setattr(self._info, field, m.group(1))

        # Cargo.toml
        elif name == "Cargo.toml":
            for field, pattern in [("display_name", r'name\s*=\s*"([^"]*)"'), ("version", r'version\s*=\s*"([^"]*)"'), ("description", r'description\s*=\s*"([^"]*)"')]:
                m = re.search(pattern, content)
                if m and not getattr(self._info, field):
                    setattr(self._info, field, m.group(1))

        # go.mod
        elif name == "go.mod":
            m = re.search(r"module\s+(\S+)", content)
            if m:
                self._info.display_name = m.group(1)

    def _detect_frameworks(self) -> None:
        """基于构建文件内容检测框架。"""
        for bf in self._info.build_files:
            bf_path = self._root / bf
            if not bf_path.exists():
                continue
            patterns = self.FRAMEWORK_PATTERNS.get(bf, {})
            if not patterns:
                continue
            try:
                content = bf_path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue

            for keyword, (fw_name, _) in patterns.items():
                if keyword.lower() in content and fw_name not in self._info.frameworks:
                    self._info.frameworks.append(fw_name)

        # 基于目录结构补充框架检测
        self._detect_frameworks_by_structure()

    def _detect_frameworks_by_structure(self) -> None:
        """基于目录结构检测框架特征。"""
        dirs = {d.name.lower() for d in self._root.rglob("*") if d.is_dir()}

        # Django
        if {"manage.py", "settings.py", "urls.py"} & {f.name for f in self._root.iterdir() if f.is_file()}:
            if "Django" not in self._info.frameworks:
                self._info.frameworks.append("Django")

        # Spring Boot
        src_dir = self._root / "src"
        if src_dir.exists():
            for java_file in src_dir.rglob("*.java"):
                try:
                    content = java_file.read_text(encoding="utf-8", errors="ignore")
                    if "@SpringBootApplication" in content:
                        if "Spring Boot" not in self._info.frameworks:
                            self._info.frameworks.append("Spring Boot")
                        if not self._info.display_name:
                            m = re.search(r"@SpringBootApplication\s*\n\s*public\s+class\s+(\w+)", content)
                            if m:
                                self._info.display_name = m.group(1)
                        break
                except Exception:
                    continue

        # .NET
        if any(f.suffix in (".csproj", ".sln", ".vbproj") for f in self._root.rglob("*")):
            if ".NET" not in self._info.frameworks:
                self._info.frameworks.append(".NET")

        # Electron
        if "electron" in dirs or any(f.name == "electron-builder.yml" for f in self._root.rglob("*")):
            if "Electron" not in self._info.frameworks:
                self._info.frameworks.append("Electron")

        # React
        if any("src/app.jsx" in str(p).lower() or "src/app.tsx" in str(p).lower() for p in self._root.rglob("App.*")):
            if "React" not in self._info.frameworks:
                self._info.frameworks.append("React")

        # Vue
        if any(f.suffix == ".vue" for f in self._root.rglob("*")):
            if "Vue.js" not in self._info.frameworks:
                self._info.frameworks.append("Vue.js")

        # Svelte
        if any(f.suffix == ".svelte" for f in self._root.rglob("*")):
            if "Svelte" not in self._info.frameworks:
                self._info.frameworks.append("Svelte")

    def _detect_databases(self) -> None:
        """检测数据库使用情况。"""
        # 从构建文件内容检测
        for bf in self._info.build_files:
            bf_path = self._root / bf
            if not bf_path.exists():
                continue
            try:
                content = bf_path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue

            for keyword, db_name in self.DB_PATTERNS.items():
                if keyword in content and db_name not in self._info.databases:
                    self._info.databases.append(db_name)

        # 从配置文件检测
        config_files = ["application.yml", "application.yaml", "application.properties",
                        "application-dev.yml", "application-prod.yml",
                        ".env", ".env.example", ".env.local", ".env.development",
                        "database.yml", "database.yaml", "config/database.yml",
                        "settings.py", "config.py", "database.ini"]
        for cf in config_files:
            cf_path = self._root / cf
            if not cf_path.exists():
                continue
            try:
                content = cf_path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            for keyword, db_name in self.DB_PATTERNS.items():
                if keyword in content and db_name not in self._info.databases:
                    self._info.databases.append(db_name)

    def _detect_architecture(self) -> None:
        """检测架构模式。"""
        # 收集所有目录名
        all_dirs = set()
        for d in self._root.rglob("*"):
            if d.is_dir():
                rel = d.relative_to(self._root)
                for part in rel.parts:
                    all_dirs.add(part.lower())

        best_match = ""
        best_score = 0

        for arch_key, arch_info in self.ARCHITECTURE_PATTERNS.items():
            score = sum(1 for ad in arch_info["dirs"] if ad in all_dirs)
            if score > best_score:
                best_score = score
                best_match = arch_info["name"]

        if best_score >= 3:
            self._info.architecture = best_match
        elif best_score >= 2:
            self._info.architecture = best_match
        elif self._info.frameworks:
            # 基于框架推断架构
            fw_set = set(self._info.frameworks)
            if "Spring Boot" in fw_set or "Django" in fw_set or "Laravel" in fw_set:
                self._info.architecture = "MVC (Model-View-Controller)"
            elif "React" in fw_set or "Vue.js" in fw_set or "Angular" in fw_set:
                self._info.architecture = "组件化架构 (Component-Based)"
            elif "FastAPI" in fw_set or "Express" in fw_set or "Gin" in fw_set:
                self._info.architecture = "RESTful API 架构"
        else:
            self._info.architecture = "简单分层架构"

    def _detect_entry_points(self) -> None:
        """检测项目入口点。"""
        entry_patterns = [
            ("main.py", "Python 入口"),
            ("app.py", "Flask/FastAPI 应用入口"),
            ("manage.py", "Django 管理入口"),
            ("index.js", "Node.js 入口"),
            ("index.ts", "TypeScript 入口"),
            ("server.js", "Node.js 服务器入口"),
            ("server.ts", "TypeScript 服务器入口"),
            ("main.go", "Go 入口"),
            ("main.rs", "Rust 入口"),
            ("index.php", "PHP 入口"),
            ("public/index.php", "PHP 入口"),
            ("Program.cs", "C# 入口"),
            ("Main.java", "Java 入口"),
            ("Application.java", "Spring Boot 入口"),
            ("App.java", "Java 应用入口"),
            ("main.swift", "Swift 入口"),
            ("main.kt", "Kotlin 入口"),
            ("main.lua", "Lua 入口"),
            ("main.dart", "Dart 入口"),
            ("src/main.rs", "Rust 入口"),
            ("src/main.go", "Go 入口"),
            ("cmd/main.go", "Go 入口"),
            ("src/main/java", "Java 源码目录"),
            ("src/index.js", "JavaScript 入口"),
            ("src/index.ts", "TypeScript 入口"),
            ("src/App.jsx", "React 入口"),
            ("src/App.tsx", "React TypeScript 入口"),
            ("src/main.tsx", "React TypeScript 入口"),
            ("src/main.jsx", "React 入口"),
            ("pages/index.tsx", "Next.js 页面入口"),
            ("pages/index.js", "Next.js 页面入口"),
            ("app/page.tsx", "Next.js App Router 入口"),
            ("app/layout.tsx", "Next.js 根布局"),
            ("src/App.vue", "Vue 入口"),
        ]

        for pattern, desc in entry_patterns:
            candidate = self._root / pattern
            if candidate.exists():
                self._info.entry_points.append(f"{pattern} ({desc})")

        # 限制数量
        if len(self._info.entry_points) > 10:
            self._info.entry_points = self._info.entry_points[:10]

    def _determine_project_type(self) -> None:
        """综合所有信息确定最终项目类型和子类型。"""
        fw_set = set(self._info.frameworks)

        # 后端框架
        if fw_set & {"Spring Boot", "Spring Cloud"}:
            self._info.project_type = "java_backend"
            self._info.project_subtype = "Spring Boot 微服务" if "Spring Cloud" in fw_set else "Spring Boot 应用"
        elif "Django" in fw_set:
            self._info.project_type = "python_backend"
            self._info.project_subtype = "Django 全栈 Web 应用"
        elif "FastAPI" in fw_set:
            self._info.project_type = "python_backend"
            self._info.project_subtype = "FastAPI 后端服务"
        elif "Flask" in fw_set:
            self._info.project_type = "python_backend"
            self._info.project_subtype = "Flask Web 应用"
        elif "Laravel" in fw_set:
            self._info.project_type = "php_backend"
            self._info.project_subtype = "Laravel Web 应用"
        elif "Ruby on Rails" in fw_set:
            self._info.project_type = "ruby_backend"
            self._info.project_subtype = "Rails Web 应用"
        elif "Gin" in fw_set or "Echo" in fw_set or "Fiber" in fw_set:
            self._info.project_type = "go_backend"
            self._info.project_subtype = "Go Web 后端"
        elif "Express" in fw_set or "Koa" in fw_set or "Fastify" in fw_set:
            self._info.project_type = "node_backend"
            self._info.project_subtype = "Node.js 后端服务"
        elif "NestJS" in fw_set:
            self._info.project_type = "node_backend"
            self._info.project_subtype = "NestJS 企业级后端"
        elif "Actix Web" in fw_set or "Axum" in fw_set or "Rocket" in fw_set:
            self._info.project_type = "rust_backend"
            self._info.project_subtype = "Rust Web 后端"
        elif ".NET" in fw_set:
            self._info.project_type = "dotnet_backend"
            self._info.project_subtype = ".NET Web 应用"
        # 前端框架
        elif "Next.js" in fw_set:
            self._info.project_type = "frontend"
            self._info.project_subtype = "Next.js 全栈前端"
        elif "React" in fw_set:
            self._info.project_type = "frontend"
            self._info.project_subtype = "React 单页应用"
        elif "Vue.js" in fw_set:
            self._info.project_type = "frontend"
            self._info.project_subtype = "Vue.js 单页应用"
        elif "Angular" in fw_set:
            self._info.project_type = "frontend"
            self._info.project_subtype = "Angular 企业级前端"
        elif "Svelte" in fw_set:
            self._info.project_type = "frontend"
            self._info.project_subtype = "Svelte 前端应用"
        # 移动端
        elif "React Native" in fw_set:
            self._info.project_type = "mobile"
            self._info.project_subtype = "React Native 移动应用"
        elif "Tauri" in fw_set:
            self._info.project_type = "desktop"
            self._info.project_subtype = "Tauri 桌面应用"
        elif "Electron" in fw_set:
            self._info.project_type = "desktop"
            self._info.project_subtype = "Electron 桌面应用"
        # 数据/AI
        elif fw_set & {"TensorFlow", "PyTorch", "Transformers", "scikit-learn", "LangChain", "LlamaIndex"}:
            self._info.project_type = "ai_ml"
            self._info.project_subtype = "AI/机器学习项目"
        # 其他
        elif self._info.language == "python":
            self._info.project_type = "python"
            self._info.project_subtype = "Python 项目"
        elif self._info.language == "java":
            self._info.project_type = "java"
            self._info.project_subtype = "Java 项目" if not self._info.project_subtype else self._info.project_subtype
        elif self._info.language == "javascript":
            self._info.project_type = "javascript"
            self._info.project_subtype = "JavaScript 项目"
        elif self._info.language == "go":
            self._info.project_type = "go"
            self._info.project_subtype = "Go 项目"
        elif self._info.language == "rust":
            self._info.project_type = "rust"
            self._info.project_subtype = "Rust 项目"
        elif self._info.language == "php":
            self._info.project_type = "php"
            self._info.project_subtype = "PHP 项目"
        elif self._info.language == "ruby":
            self._info.project_type = "ruby"
            self._info.project_subtype = "Ruby 项目"
        else:
            self._info.project_type = self._info.project_type or "generic"
            self._info.project_subtype = self._info.project_subtype or "通用项目"

        # 如果没有 display_name，用目录名
        if not self._info.display_name:
            self._info.display_name = self._root.name

    def _build_tech_stack(self) -> None:
        """构建技术栈分类汇总。"""
        stack: dict[str, list[str]] = {}

        if self._info.language:
            lang_display = {
                "python": "Python", "java": "Java", "javascript": "JavaScript",
                "typescript": "TypeScript", "go": "Go", "rust": "Rust",
                "php": "PHP", "ruby": "Ruby", "c": "C", "cpp": "C++",
                "csharp": "C#", "kotlin": "Kotlin", "swift": "Swift",
                "scala": "Scala", "elixir": "Elixir", "dart": "Dart",
                "haskell": "Haskell", "clojure": "Clojure", "erlang": "Erlang",
                "zig": "Zig", "perl": "Perl", "lua": "Lua", "nim": "Nim",
                "solidity": "Solidity", "groovy": "Groovy", "rlang": "R",
                "objective_c": "Objective-C",
            }
            stack["语言"] = [lang_display.get(self._info.language, self._info.language)]

        if self._info.frameworks:
            stack["框架"] = self._info.frameworks

        if self._info.build_tools:
            stack["构建工具"] = self._info.build_tools

        if self._info.databases:
            stack["数据库"] = self._info.databases

        self._info.tech_stack = stack