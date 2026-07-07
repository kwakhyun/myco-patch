from __future__ import annotations

import json
import os
from pathlib import Path

from mycopatch.core.models import (
    EcosystemFinding,
    FrameworkHint,
    VerificationProfile,
    relative_path,
)
from mycopatch.core.paths import IGNORED_DIRS


MAX_MANIFEST_BYTES = 512_000

SOURCE_SUFFIXES = {
    "python": {".py"},
    "javascript-typescript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"},
    "go": {".go"},
    "rust": {".rs"},
    "java-kotlin": {".java", ".kt", ".kts"},
    "dotnet": {".cs", ".fs", ".vb"},
    "ruby": {".rb"},
    "php": {".php"},
}


def detect_ecosystems(repo_root: Path | str) -> list[EcosystemFinding]:
    root = Path(repo_root).resolve()
    files = _walk_repo_files(root)
    source_counts = _source_counts(files)
    by_name = {path.name: path for path in files}

    ecosystems = [
        _python_ecosystem(root, files, by_name, source_counts),
        _js_ts_ecosystem(root, files, by_name, source_counts),
        _go_ecosystem(root, files, by_name, source_counts),
        _rust_ecosystem(root, files, by_name, source_counts),
        _java_kotlin_ecosystem(root, files, by_name, source_counts),
        _dotnet_ecosystem(root, files, source_counts),
        _ruby_ecosystem(root, files, by_name, source_counts),
        _php_ecosystem(root, files, by_name, source_counts),
    ]
    return [ecosystem for ecosystem in ecosystems if ecosystem is not None]


def _python_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"pyproject.toml", "setup.cfg", "setup.py", "requirements.txt", "pytest.ini", "tox.ini"})
    if not manifests and source_counts["python"] == 0:
        return None

    text = _joined_manifest_text(root, manifests)
    frameworks = _framework_hints(
        "python",
        [
            ("django", "django", "high"),
            ("fastapi", "fastapi", "high"),
            ("flask", "flask", "high"),
            ("pytest", "pytest", "medium"),
        ],
        text,
    )
    if "manage.py" in by_name and not _has_hint(frameworks, "django"):
        frameworks.append(FrameworkHint(name="django", ecosystem="python", source="manage.py", confidence="high"))
    if "pytest.ini" in by_name and not _has_hint(frameworks, "pytest"):
        frameworks.append(FrameworkHint(name="pytest", ecosystem="python", source="pytest.ini", confidence="high"))

    return EcosystemFinding(
        name="python",
        language="Python",
        manifest_paths=manifests,
        framework_hints=sorted(frameworks, key=lambda item: item.name),
        test_runner_candidates=["pytest"],
        verification_profiles=[
            VerificationProfile(
                id="python-pytest",
                ecosystem="python",
                command=["pytest"],
                description="Run the repository pytest suite without installing dependencies.",
            )
        ],
    )


def _js_ts_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"package.json", "tsconfig.json", "jsconfig.json"})
    if not manifests and source_counts["javascript-typescript"] == 0:
        return None

    package = _read_package_json(by_name.get("package.json"))
    deps = _package_dependencies(package)
    frameworks: list[FrameworkHint] = []
    for package_name, hint_name in {
        "next": "next",
        "react": "react",
        "vue": "vue",
        "svelte": "svelte",
        "nuxt": "nuxt",
        "express": "express",
        "fastify": "fastify",
        "@nestjs/core": "nestjs",
    }.items():
        if package_name in deps:
            frameworks.append(FrameworkHint(name=hint_name, ecosystem="javascript-typescript", source="package.json", confidence="high"))

    test_candidates = ["node:test"]
    for package_name, runner in {"jest": "jest", "vitest": "vitest", "mocha": "mocha", "ava": "ava"}.items():
        if package_name in deps:
            test_candidates.append(runner)

    return EcosystemFinding(
        name="javascript-typescript",
        language="JavaScript/TypeScript",
        manifest_paths=manifests,
        framework_hints=sorted(frameworks, key=lambda item: item.name),
        test_runner_candidates=test_candidates,
        verification_profiles=[
            VerificationProfile(
                id="js-ts-node-test",
                ecosystem="javascript-typescript",
                command=["node", "--test"],
                description="Run Node's built-in test runner without invoking package managers.",
            )
        ],
    )


def _go_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"go.mod", "go.sum"})
    if not manifests and source_counts["go"] == 0:
        return None

    text = _read_manifest(by_name.get("go.mod"))
    frameworks = _framework_hints(
        "go",
        [
            ("github.com/gin-gonic/gin", "gin", "high"),
            ("github.com/labstack/echo", "echo", "high"),
            ("github.com/gofiber/fiber", "fiber", "high"),
        ],
        text,
    )
    return EcosystemFinding(
        name="go",
        language="Go",
        manifest_paths=manifests,
        framework_hints=frameworks,
        test_runner_candidates=["go test"],
        verification_profiles=[
            VerificationProfile(
                id="go-test",
                ecosystem="go",
                command=["go", "test", "./..."],
                description="Run Go tests for all packages.",
            )
        ],
    )


def _rust_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"Cargo.toml", "Cargo.lock"})
    if not manifests and source_counts["rust"] == 0:
        return None

    text = _read_manifest(by_name.get("Cargo.toml"))
    frameworks = _framework_hints(
        "rust",
        [
            ("actix-web", "actix-web", "high"),
            ("axum", "axum", "high"),
            ("rocket", "rocket", "high"),
        ],
        text,
    )
    return EcosystemFinding(
        name="rust",
        language="Rust",
        manifest_paths=manifests,
        framework_hints=frameworks,
        test_runner_candidates=["cargo test"],
        verification_profiles=[
            VerificationProfile(
                id="rust-cargo-test",
                ecosystem="rust",
                command=["cargo", "test", "--offline"],
                description="Run cargo tests in offline mode.",
            )
        ],
    )


def _java_kotlin_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"})
    if not manifests and source_counts["java-kotlin"] == 0:
        return None

    text = _joined_manifest_text(root, manifests)
    frameworks = _framework_hints(
        "java-kotlin",
        [
            ("spring-boot", "spring-boot", "high"),
            ("org.springframework.boot", "spring-boot", "high"),
            ("quarkus", "quarkus", "high"),
            ("micronaut", "micronaut", "high"),
        ],
        text,
    )
    profiles: list[VerificationProfile] = []
    candidates: list[str] = []
    if "pom.xml" in by_name:
        candidates.append("maven test")
        profiles.append(
            VerificationProfile(
                id="java-maven-test",
                ecosystem="java-kotlin",
                command=["mvn", "test", "-o"],
                description="Run Maven tests in offline mode.",
            )
        )
    if "build.gradle" in by_name or "build.gradle.kts" in by_name:
        candidates.append("gradle test")
        profiles.append(
            VerificationProfile(
                id="java-gradle-test",
                ecosystem="java-kotlin",
                command=["gradle", "test", "--offline"],
                description="Run Gradle tests in offline mode.",
            )
        )

    return EcosystemFinding(
        name="java-kotlin",
        language="Java/Kotlin",
        manifest_paths=manifests,
        framework_hints=frameworks,
        test_runner_candidates=candidates,
        verification_profiles=profiles,
    )


def _dotnet_ecosystem(
    root: Path,
    files: list[Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = sorted(
        relative_path(path, root)
        for path in files
        if path.suffix in {".sln", ".csproj", ".fsproj", ".vbproj"}
    )
    if not manifests and source_counts["dotnet"] == 0:
        return None

    text = _joined_manifest_text(root, manifests)
    frameworks = _framework_hints(
        "dotnet",
        [
            ("microsoft.aspnetcore", "asp.net-core", "high"),
            ("xunit", "xunit", "medium"),
            ("nunit", "nunit", "medium"),
            ("mstest", "mstest", "medium"),
        ],
        text,
    )
    return EcosystemFinding(
        name="dotnet",
        language=".NET",
        manifest_paths=manifests,
        framework_hints=frameworks,
        test_runner_candidates=["dotnet test"],
        verification_profiles=[
            VerificationProfile(
                id="dotnet-test",
                ecosystem="dotnet",
                command=["dotnet", "test", "--no-restore"],
                description="Run .NET tests without restoring packages.",
            )
        ],
    )


def _ruby_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"Gemfile", "Gemfile.lock", ".ruby-version"})
    if not manifests and source_counts["ruby"] == 0:
        return None

    text = _joined_manifest_text(root, manifests)
    frameworks = _framework_hints(
        "ruby",
        [
            ("rails", "rails", "high"),
            ("sinatra", "sinatra", "high"),
            ("rspec", "rspec", "medium"),
        ],
        text,
    )
    profiles = []
    candidates = []
    if "Gemfile" in by_name or "Gemfile.lock" in by_name:
        candidates.append("rspec")
        profiles.append(
            VerificationProfile(
                id="ruby-rspec",
                ecosystem="ruby",
                command=["bundle", "exec", "rspec"],
                description="Run RSpec through Bundler without installing gems.",
            )
        )
    return EcosystemFinding(
        name="ruby",
        language="Ruby",
        manifest_paths=manifests,
        framework_hints=frameworks,
        test_runner_candidates=candidates,
        verification_profiles=profiles,
    )


def _php_ecosystem(
    root: Path,
    files: list[Path],
    by_name: dict[str, Path],
    source_counts: dict[str, int],
) -> EcosystemFinding | None:
    manifests = _existing_named(files, root, {"composer.json", "composer.lock", "phpunit.xml", "phpunit.xml.dist"})
    if not manifests and source_counts["php"] == 0:
        return None

    text = _joined_manifest_text(root, manifests)
    frameworks = _framework_hints(
        "php",
        [
            ("laravel/framework", "laravel", "high"),
            ("symfony/framework-bundle", "symfony", "high"),
            ("phpunit", "phpunit", "medium"),
        ],
        text,
    )
    return EcosystemFinding(
        name="php",
        language="PHP",
        manifest_paths=manifests,
        framework_hints=frameworks,
        test_runner_candidates=["phpunit"],
        verification_profiles=[
            VerificationProfile(
                id="php-phpunit",
                ecosystem="php",
                command=["vendor/bin/phpunit"],
                description="Run the project-local PHPUnit binary if dependencies are already installed.",
            )
        ],
    )


def _walk_repo_files(root: Path) -> list[Path]:
    results: list[Path] = []
    for current_root_raw, dirnames, filenames in os.walk(root):
        current_root = Path(current_root_raw)
        dirnames[:] = sorted(
            directory for directory in dirnames if directory not in IGNORED_DIRS
        )
        for filename in sorted(filenames):
            path = current_root / filename
            if path.name.endswith(".d.ts"):
                continue
            results.append(path)
    return results


def _source_counts(files: list[Path]) -> dict[str, int]:
    counts = {ecosystem: 0 for ecosystem in SOURCE_SUFFIXES}
    for path in files:
        for ecosystem, suffixes in SOURCE_SUFFIXES.items():
            if path.suffix in suffixes:
                counts[ecosystem] += 1
    return counts


def _existing_named(files: list[Path], root: Path, names: set[str]) -> list[str]:
    return sorted(relative_path(path, root) for path in files if path.name in names)


def _joined_manifest_text(root: Path, manifest_paths: list[str]) -> str:
    chunks = []
    for rel_path in manifest_paths:
        chunks.append(_read_manifest(root / rel_path))
    return "\n".join(chunks).lower()


def _read_manifest(path: Path | None) -> str:
    if path is None or not path.exists() or path.stat().st_size > MAX_MANIFEST_BYTES:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _read_package_json(path: Path | None) -> dict:
    raw = _read_manifest(path)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _package_dependencies(package: dict) -> set[str]:
    dependencies: set[str] = set()
    for key in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
        value = package.get(key, {})
        if isinstance(value, dict):
            dependencies.update(name.lower() for name in value)
    return dependencies


def _framework_hints(
    ecosystem: str,
    patterns: list[tuple[str, str, str]],
    text: str,
) -> list[FrameworkHint]:
    hints = []
    lowered = text.lower()
    for pattern, name, confidence in patterns:
        if pattern.lower() in lowered:
            hints.append(
                FrameworkHint(
                    name=name,
                    ecosystem=ecosystem,
                    source="manifest",
                    confidence=confidence,  # type: ignore[arg-type]
                )
            )
    return sorted(_dedupe_hints(hints), key=lambda item: item.name)


def _dedupe_hints(hints: list[FrameworkHint]) -> list[FrameworkHint]:
    deduped: dict[tuple[str, str], FrameworkHint] = {}
    for hint in hints:
        key = (hint.ecosystem, hint.name)
        existing = deduped.get(key)
        if existing is None or _confidence_rank(hint.confidence) > _confidence_rank(existing.confidence):
            deduped[key] = hint
    return list(deduped.values())


def _has_hint(hints: list[FrameworkHint], name: str) -> bool:
    return any(hint.name == name for hint in hints)


def _confidence_rank(confidence: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[confidence]
