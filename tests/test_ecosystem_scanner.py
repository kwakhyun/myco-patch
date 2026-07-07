from mycopatch.core.ecosystem_scanner import detect_ecosystems


def test_detects_popular_language_and_framework_ecosystems(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["django", "pytest"]\n', encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"next":"1.0.0","react":"1.0.0"},"devDependencies":{"jest":"1.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "go.mod").write_text("module example\nrequire github.com/gin-gonic/gin v1.0.0\n", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text('[dependencies]\naxum = "0.7"\n', encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project><dependency>spring-boot</dependency></project>\n", encoding="utf-8")
    (tmp_path / "app.csproj").write_text("<PackageReference Include=\"Microsoft.AspNetCore\" />\n", encoding="utf-8")
    (tmp_path / "Gemfile").write_text("gem 'rails'\ngem 'rspec'\n", encoding="utf-8")
    (tmp_path / "composer.json").write_text('{"require":{"laravel/framework":"^11"},"require-dev":{"phpunit/phpunit":"^10"}}', encoding="utf-8")

    ecosystems = detect_ecosystems(tmp_path)
    by_name = {ecosystem.name: ecosystem for ecosystem in ecosystems}

    assert list(by_name) == [
        "python",
        "javascript-typescript",
        "go",
        "rust",
        "java-kotlin",
        "dotnet",
        "ruby",
        "php",
    ]
    assert _hint_names(by_name["python"]) == {"django", "pytest"}
    assert {"next", "react"} <= _hint_names(by_name["javascript-typescript"])
    assert _hint_names(by_name["go"]) == {"gin"}
    assert _hint_names(by_name["rust"]) == {"axum"}
    assert _hint_names(by_name["java-kotlin"]) == {"spring-boot"}
    assert _hint_names(by_name["dotnet"]) == {"asp.net-core"}
    assert {"rails", "rspec"} <= _hint_names(by_name["ruby"])
    assert {"laravel", "phpunit"} <= _hint_names(by_name["php"])
    assert by_name["go"].verification_profiles[0].command == ["go", "test", "./..."]


def test_ecosystem_scanner_ignores_build_and_vendor_directories(tmp_path):
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "composer.json").write_text('{"require":{"laravel/framework":"^11"}}', encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()
    (target / "Cargo.toml").write_text("[package]\nname='ignored'\n", encoding="utf-8")

    ecosystems = detect_ecosystems(tmp_path)

    assert ecosystems == []


def _hint_names(ecosystem):
    return {hint.name for hint in ecosystem.framework_hints}
