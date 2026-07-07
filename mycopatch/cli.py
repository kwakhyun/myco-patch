from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mycopatch.core.config import load_config
from mycopatch.core.cost import record_cost_event
from mycopatch.core.explainer import explain_risk
from mycopatch.core.memory import append_memory_event, read_memory_events
from mycopatch.core.models import RepoScanResult, RiskFinding
from mycopatch.core.patch_recommender import create_patch_recommendations
from mycopatch.core.paths import ensure_myco_layout, get_paths, is_initialized
from mycopatch.core.probe_generator import generate_timezone_probe
from mycopatch.core.repo_scanner import scan_repository
from mycopatch.core.reporter import (
    build_console_report,
    write_immune_history,
    write_repo_weather,
)
from mycopatch.core.risk_mapper import map_repo_risks
from mycopatch.core.spore_loader import load_builtin_spores, load_spores
from mycopatch.core.verification import select_verification_profiles, verify_profile
from mycopatch.core.verifier import verify_probe
from mycopatch.providers.service import invoke_model_provider


app = typer.Typer(help="MycoPatch: an offline immune system for codebases.")
spores_app = typer.Typer(help="Inspect available spores.")
app.add_typer(spores_app, name="spores")
console = Console()


class HuntMode(str, Enum):
    safe = "safe"
    aggressive = "aggressive"


class LanguageFilter(str, Enum):
    all = "all"
    python = "python"
    javascript = "javascript"
    typescript = "typescript"
    js_ts = "js-ts"


@app.command()
def init() -> None:
    """Create the .myco directory structure and install built-in spores."""
    already_initialized = is_initialized(Path.cwd())
    paths = ensure_myco_layout(Path.cwd())
    if already_initialized:
        console.print(f"[green]MycoPatch already initialized; verified layout at[/green] {_display_path(paths.myco)}")
        return

    append_memory_event(
        paths.repo_root,
        "repo_initialized",
        {"myco_dir": paths.myco.relative_to(paths.repo_root).as_posix()},
    )
    console.print(f"[green]Initialized MycoPatch at[/green] {_display_path(paths.myco)}")


@app.command()
def scan(
    json_output: bool = typer.Option(False, "--json", help="Print a machine-readable JSON summary."),
) -> None:
    """Scan the repository and write a repo weather report."""
    _require_initialized()
    root = Path.cwd().resolve()
    scan_result = scan_repository(root)
    risks = map_repo_risks(scan_result)
    append_memory_event(
        root,
        "scan_completed",
        {
            "python_files": scan_result.python_file_count,
            "js_ts_files": scan_result.js_ts_file_count,
            "ecosystems": [ecosystem.name for ecosystem in scan_result.ecosystems],
            "test_files": scan_result.test_file_count,
            "risk_count": len(risks),
        },
    )
    append_memory_event(
        root,
        "ecosystems_detected",
        {
            "count": len(scan_result.ecosystems),
            "ecosystems": [ecosystem.json_dict() for ecosystem in scan_result.ecosystems],
        },
    )
    for risk in risks:
        append_memory_event(root, "risk_detected", risk.json_dict())
    record_cost_event(
        root,
        input_text=" ".join(finding.path for finding in scan_result.source_files),
        output_text=f"repo weather report with {len(risks)} risk(s)",
        notes="repo scan and weather report",
    )
    report_path = write_repo_weather(root, scan_result, risks)
    if json_output:
        typer.echo(json.dumps(_scan_json_payload(scan_result, risks, report_path), sort_keys=True))
        return

    console.print(
        f"[green]Scan complete.[/green] Python files: {scan_result.python_file_count}, "
        f"JS/TS files: {scan_result.js_ts_file_count}, ecosystems: {len(scan_result.ecosystems)}, "
        f"tests: {scan_result.test_file_count}, risks: {len(risks)}"
    )
    console.print(f"Report: {_display_path(report_path)}")


@app.command()
def ecosystems(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON ecosystem findings."),
) -> None:
    """Print detected languages, frameworks, manifests, and verification candidates."""
    _require_initialized()
    root = Path.cwd().resolve()
    scan_result = scan_repository(root)
    append_memory_event(
        root,
        "ecosystems_detected",
        {
            "count": len(scan_result.ecosystems),
            "ecosystems": [ecosystem.json_dict() for ecosystem in scan_result.ecosystems],
        },
    )

    if json_output:
        typer.echo(json.dumps([ecosystem.json_dict() for ecosystem in scan_result.ecosystems], sort_keys=True))
        return

    if not scan_result.ecosystems:
        console.print("[yellow]No supported ecosystem manifests or source files detected.[/yellow]")
        return

    _print_ecosystem_table(scan_result.ecosystems)


@app.command()
def verify(
    ecosystem: str = typer.Option("all", "--ecosystem", "-e", help="Ecosystem name to verify, or all."),
    profile: str | None = typer.Option(None, "--profile", help="Run only a specific verification profile id."),
    run: bool = typer.Option(False, "--run/--no-run", help="Execute selected project test profiles. Default is dry-run."),
    allow_project_tests: bool = typer.Option(
        False,
        "--allow-project-tests",
        help="Explicitly allow safe project test commands selected by MycoPatch.",
    ),
    timeout: int | None = typer.Option(None, min=1, help="Override profile timeout in seconds."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON verification results."),
) -> None:
    """Dry-run or execute safe project verification profiles."""
    _require_initialized()
    root = Path.cwd().resolve()
    config = _load_config_or_exit(root)
    scan_result = scan_repository(root)
    profiles = select_verification_profiles(scan_result.ecosystems, ecosystem_name=ecosystem, profile_id=profile)
    effective_allow = allow_project_tests or config.allow_project_test_commands

    if not profiles:
        if json_output:
            typer.echo("[]")
            return
        console.print("[yellow]No verification profiles matched the requested filters.[/yellow]")
        console.print("Run `myco ecosystems` to inspect detected candidates.")
        return

    results = []
    for selected_profile in profiles:
        append_memory_event(root, "verification_profile_selected", selected_profile.json_dict())
        result = verify_profile(
            root,
            selected_profile,
            run=run,
            allow_project_tests=effective_allow,
            timeout_seconds=timeout,
        )
        results.append(result)
        append_memory_event(
            root,
            f"verification_{result.status}",
            result.json_dict(),
        )
        record_cost_event(
            root,
            input_text=" ".join(selected_profile.command),
            output_text=result.status,
            notes=f"offline verification profile {selected_profile.id}",
        )

    if json_output:
        typer.echo(json.dumps([result.json_dict() for result in results], sort_keys=True))
        return

    _print_verification_table(results)
    if not run:
        console.print("[yellow]Dry run only.[/yellow] Add `--run --allow-project-tests` to execute selected profiles.")
    elif not effective_allow:
        console.print("[yellow]Project test execution was not explicitly allowed.[/yellow]")


@app.command()
def hunt(
    budget: int = typer.Option(30000, help="Estimated token budget for this hunt."),
    run: bool = typer.Option(True, "--run/--no-run", help="Run generated probes with pytest or node:test."),
    mode: HuntMode = typer.Option(HuntMode.safe, help="Probe generation mode: safe or aggressive."),
    language: LanguageFilter = typer.Option(
        LanguageFilter.all,
        "--language",
        "-l",
        help="Limit probe candidates by language.",
    ),
    target_file: str | None = typer.Option(
        None,
        "--file",
        help="Limit probe candidates to a repository-relative file path or basename.",
    ),
    limit: int = typer.Option(1, min=1, help="Maximum number of probes to generate unless --all is used."),
    all_risks: bool = typer.Option(False, "--all", help="Generate probes for every matching risk."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview selected risks without generating probe files."),
) -> None:
    """Generate and optionally verify probes from loaded spores."""
    _require_initialized()
    root = Path.cwd().resolve()
    mode_value = mode.value
    scan_result = scan_repository(root)
    risks = map_repo_risks(scan_result)
    spores = load_spores(root)

    if not risks:
        console.print("[yellow]No clear MycoPatch risk target found.[/yellow]")
        append_memory_event(root, "probe_inconclusive", {"reason": "no clear target"})
        record_cost_event(root, input_text=scan_result.model_dump_json(), budget_limit=budget, notes="inconclusive hunt")
        return

    matching_risks = _filter_risks(risks, language, target_file)
    selected_risks = matching_risks if all_risks else matching_risks[:limit]
    if not selected_risks:
        console.print("[yellow]No MycoPatch risks matched the requested filters.[/yellow]")
        if not dry_run:
            append_memory_event(
                root,
                "probe_inconclusive",
                {
                    "reason": "no matching target",
                    "language": language.value,
                    "file": target_file,
                },
            )
        return

    if dry_run:
        _print_risk_table(selected_risks, title="MycoPatch Hunt Dry Run")
        console.print("[yellow]Dry run only; no probe files were generated.[/yellow]")
        return

    _load_config_or_exit(root)
    for risk in selected_risks:
        spore = _spore_for_risk(spores, risk)
        if spore is None:
            console.print(f"[yellow]No spore is available for {risk.risk_type}.[/yellow]")
            append_memory_event(root, "probe_inconclusive", {"reason": f"missing spore for {risk.risk_type}"})
            continue

        probe_ideas = invoke_model_provider(
            root,
            task="suggest_probe_ideas",
            prompt=risk.model_dump_json(),
        )
        probe = generate_timezone_probe(root, risk, spore, mode=mode_value)
        append_memory_event(
            root,
            "probe_generated",
            {
                "probe": probe.json_dict(),
                "risk": risk.json_dict(),
                "provider_probe_ideas": probe_ideas.json_dict(),
            },
        )
        record_cost_event(
            root,
            input_text=scan_result.model_dump_json() + risk.model_dump_json(),
            output_text=probe.model_dump_json(),
            budget_limit=budget,
            notes=f"offline heuristic {mode_value} probe generation",
        )

        if not run:
            append_memory_event(root, "probe_inconclusive", {"probe": probe.json_dict(), "reason": "verification disabled"})
            console.print(f"[yellow]Probe generated but not run:[/yellow] {probe.path}")
            continue

        result = verify_probe(root, probe, timeout_seconds=spore.budget.max_runtime_seconds)
        append_memory_event(
            root,
            f"probe_{result.status}",
            {"probe": probe.json_dict(), "result": result.json_dict()},
        )
        if result.status == "passed":
            console.print(f"[green]Probe passed:[/green] {probe.path}")
        elif result.status == "failed":
            console.print(f"[red]Probe failed reproducibly:[/red] {probe.path}")
            if probe.mode == "aggressive" and probe.explanation_path:
                console.print(f"Aggressive probe report: {probe.explanation_path}")
        else:
            console.print(f"[yellow]Probe {result.status}:[/yellow] {probe.path}")


@app.command()
def risks(
    limit: int = typer.Option(10, min=1, help="Maximum number of risk findings to show."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON findings."),
) -> None:
    """Print top risk findings without generating probes."""
    _require_initialized()
    root = Path.cwd().resolve()
    scan_result = scan_repository(root)
    findings = map_repo_risks(scan_result)
    selected = findings[:limit]

    if not findings:
        if json_output:
            typer.echo("[]")
            return
        console.print("[green]No clear MycoPatch risks detected.[/green]")
        return

    if json_output:
        typer.echo(json.dumps([risk.json_dict() for risk in selected], sort_keys=True))
        return

    _print_risk_table(selected)


@app.command()
def explain(
    limit: int = typer.Option(5, min=1, help="Maximum number of risk explanations to show."),
    target_file: str | None = typer.Option(None, "--file", help="Explain risks for a repository-relative file path or basename."),
    risk_type: str | None = typer.Option(None, "--risk-type", help="Explain only a specific risk type."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON explanations."),
) -> None:
    """Explain why detected risks matter."""
    _require_initialized()
    root = Path.cwd().resolve()
    scan_result = scan_repository(root)
    findings = [
        risk
        for risk in map_repo_risks(scan_result)
        if _file_matches(risk, target_file) and _risk_type_matches(risk, risk_type)
    ][:limit]

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "risk": risk.json_dict(),
                        "explanation": explain_risk(risk),
                    }
                    for risk in findings
                ],
                sort_keys=True,
            )
        )
        return

    if not findings:
        console.print("[green]No matching MycoPatch risks to explain.[/green]")
        return

    for risk in findings:
        console.print(f"[bold]{risk.file_path}[/bold] ({risk.risk_type}, {risk.confidence})")
        console.print(explain_risk(risk))
        if risk.evidence:
            console.print("Evidence:")
            for item in risk.evidence[:4]:
                console.print(f"- {item}")
        if risk.recommended_review_steps:
            console.print("Human review:")
            for step in risk.recommended_review_steps[:4]:
                console.print(f"- {step}")
        console.print("")


@app.command()
def report() -> None:
    """Print a consolidated immune report."""
    _require_initialized()
    root = Path.cwd().resolve()
    write_immune_history(root)
    report_data = build_console_report(root)

    table = Table(title="MycoPatch Immune Report")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Memory events", str(report_data["memory_events"]))
    table.add_row("Probes generated", str(report_data["probes_generated"]))
    table.add_row("Probe files", str(report_data["probe_files"]))
    table.add_row("Passed probes", str(report_data["passed_probes"]))
    table.add_row("Failed probes", str(report_data["failed_probes"]))
    table.add_row("Inconclusive probes", str(report_data["inconclusive_probes"]))
    table.add_row("Ecosystem detection events", str(report_data["ecosystems_detected"]))
    table.add_row("Verification dry runs", str(report_data["verification_dry_run"]))
    table.add_row("Verification passed", str(report_data["verification_passed"]))
    table.add_row("Verification failed", str(report_data["verification_failed"]))
    table.add_row("Verification skipped", str(report_data["verification_skipped"]))
    table.add_row("Verification blocked", str(report_data["verification_blocked"]))
    cost = report_data["cost"]
    table.add_row("Estimated input tokens", str(cost["estimated_input_tokens"]))
    table.add_row("Estimated output tokens", str(cost["estimated_output_tokens"]))
    table.add_row("Estimated cost USD", f"{cost['estimated_cost_usd']:.4f}")
    console.print(table)
    console.print(
        "Suggested next action: run `myco risks`, then `myco hunt --budget 30000 --mode safe` "
        "or inspect `.myco/reports/`."
    )


@app.command()
def patch() -> None:
    """Create manual patch recommendations from reproducible failures."""
    _require_initialized()
    root = Path.cwd().resolve()
    _load_config_or_exit(root)
    recommendations = create_patch_recommendations(root)
    paths = get_paths(root)
    if recommendations:
        console.print(f"[green]Created {len(recommendations)} recommendation(s).[/green]")
    else:
        console.print("[yellow]No reproducible failures recorded; wrote an empty recommendation report.[/yellow]")
    console.print(f"Report: {_display_path(paths.patch_recommendations)}")


@app.command("memory")
def memory_command(
    event_type: str | None = typer.Option(None, "--type", help="Filter memory events by event type."),
    limit: int = typer.Option(20, min=1, help="Maximum number of recent memory events to show."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON memory events."),
) -> None:
    """Inspect append-only MycoPatch memory events."""
    _require_initialized()
    root = Path.cwd().resolve()
    events = read_memory_events(root)
    if event_type is not None:
        events = [event for event in events if event.event_type == event_type]
    selected = events[-limit:]

    if json_output:
        typer.echo(json.dumps([event.json_dict() for event in selected], sort_keys=True))
        return

    if not selected:
        console.print("[yellow]No matching memory events found.[/yellow]")
        return

    table = Table(title="MycoPatch Memory")
    table.add_column("Created")
    table.add_column("Event")
    table.add_column("Summary")
    for event in selected:
        table.add_row(
            event.created_at.isoformat(),
            event.event_type,
            _memory_summary(event.payload),
        )
    console.print(table)


@spores_app.command("list")
def list_spores() -> None:
    """List built-in and repo-local spores."""
    table = Table(title="MycoPatch Spores")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Language")
    table.add_column("Source")
    for spore in load_spores(Path.cwd()):
        table.add_row(spore.name, spore.version, spore.language, spore.source)
    console.print(table)


@app.command()
def doctor() -> None:
    """Check local MycoPatch setup."""
    root = Path.cwd().resolve()
    initialized = is_initialized(root)
    builtin_spores = load_builtin_spores()
    local_spores = [spore for spore in load_spores(root) if spore.source == "local"] if initialized else []
    config, config_error = _try_load_config(root)
    table = Table(title="MycoPatch Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_row(".myco initialized", "yes" if initialized else "no")
    for tool in ["pytest", "node", "go", "cargo", "mvn", "gradle", "dotnet", "ruby", "bundle", "php"]:
        table.add_row(f"{tool} available", "yes" if _tool_available(tool) else "no")
    table.add_row("vendor/bin/phpunit available", "yes" if (root / "vendor" / "bin" / "phpunit").exists() else "no")
    table.add_row("built-in spores", str(len(builtin_spores)))
    table.add_row("local spores", str(len(local_spores)))
    table.add_row("config valid", "yes" if config_error is None else f"no: {config_error}")
    if config is not None:
        table.add_row("provider", config.default_provider)
        table.add_row("provider network", "enabled" if config.allow_network_for_model_provider else "disabled")
        table.add_row("project tests", "enabled" if config.allow_project_test_commands else "explicit flag required")
    console.print(table)


def _require_initialized() -> None:
    if not is_initialized(Path.cwd()):
        console.print(
            "[red]MycoPatch is not initialized in the current directory.[/red]\n"
            f"Current directory: {Path.cwd()}\n"
            "Run `myco init` from the repository root, then retry this command."
        )
        raise typer.Exit(code=1)


def _try_load_config(root: Path):
    try:
        return load_config(root), None
    except ValueError as exc:
        return None, str(exc)


def _load_config_or_exit(root: Path):
    config, error = _try_load_config(root)
    if error is not None:
        console.print(f"[red]Invalid MycoPatch config.[/red]\n{error}\nRun `myco doctor` for diagnostics.")
        raise typer.Exit(code=1)
    return config


def _filter_risks(
    risks: list[RiskFinding],
    language: LanguageFilter,
    target_file: str | None,
) -> list[RiskFinding]:
    return [
        risk
        for risk in risks
        if _language_matches(risk, language) and _file_matches(risk, target_file)
    ]


def _language_matches(risk: RiskFinding, language: LanguageFilter) -> bool:
    if language == LanguageFilter.all:
        return True
    if language == LanguageFilter.js_ts:
        return risk.language in {"javascript", "typescript"}
    return risk.language == language.value


def _file_matches(risk: RiskFinding, target_file: str | None) -> bool:
    if target_file is None:
        return True
    normalized = target_file.replace("\\", "/").lstrip("./")
    return risk.file_path == normalized or Path(risk.file_path).name == normalized


def _risk_type_matches(risk: RiskFinding, risk_type: str | None) -> bool:
    return risk_type is None or risk.risk_type == risk_type


def _memory_summary(payload: dict) -> str:
    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    risk = payload.get("risk") if isinstance(payload.get("risk"), dict) else {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    for source in [probe, risk, result, payload]:
        for key in ["target_file", "file_path", "probe_path", "path", "reason"]:
            value = source.get(key) if isinstance(source, dict) else None
            if value:
                return str(value)
    if "count" in payload:
        return f"count={payload['count']}"
    return "-"


def _print_risk_table(risks: list[RiskFinding], title: str = "MycoPatch Top Risks") -> None:
    table = Table(title=title)
    table.add_column("Score", justify="right")
    table.add_column("Confidence")
    table.add_column("Language")
    table.add_column("Nearby Test")
    table.add_column("File")
    table.add_column("Evidence")
    for risk in risks:
        table.add_row(
            str(risk.score),
            risk.confidence,
            risk.language,
            "yes" if risk.nearby_test_detected else "no",
            risk.file_path,
            risk.evidence[0] if risk.evidence else "no line-level evidence",
        )
    console.print(table)


def _print_ecosystem_table(ecosystems) -> None:
    table = Table(title="MycoPatch Ecosystems")
    table.add_column("Ecosystem")
    table.add_column("Language")
    table.add_column("Manifests", overflow="fold")
    table.add_column("Frameworks", overflow="fold")
    table.add_column("Verification Profiles", overflow="fold")
    for ecosystem in ecosystems:
        table.add_row(
            ecosystem.name,
            ecosystem.language,
            ", ".join(ecosystem.manifest_paths) if ecosystem.manifest_paths else "source-only",
            ", ".join(hint.name for hint in ecosystem.framework_hints) if ecosystem.framework_hints else "none detected",
            ", ".join(profile.id for profile in ecosystem.verification_profiles) if ecosystem.verification_profiles else "none",
        )
    console.print(table)


def _print_verification_table(results) -> None:
    table = Table(title="MycoPatch Verification")
    table.add_column("Status")
    table.add_column("Ecosystem")
    table.add_column("Profile")
    table.add_column("Command")
    table.add_column("Evidence")
    for result in results:
        table.add_row(
            result.status,
            result.ecosystem,
            result.profile_id,
            _format_command(result.command),
            result.evidence[0] if result.evidence else "-",
        )
    console.print(table)


def _scan_json_payload(
    scan_result: RepoScanResult,
    risks: list[RiskFinding],
    report_path: Path,
) -> dict:
    return {
        "repo_path": ".",
        "python_files": scan_result.python_file_count,
        "js_ts_files": scan_result.js_ts_file_count,
        "ecosystems": [ecosystem.json_dict() for ecosystem in scan_result.ecosystems],
        "test_files": scan_result.test_file_count,
        "framework_hints": scan_result.framework_hints,
        "risk_count": len(risks),
        "top_risks": [risk.json_dict() for risk in risks[:10]],
        "report_path": report_path.relative_to(Path.cwd().resolve()).as_posix(),
    }


def _format_command(command: list[str]) -> str:
    return " ".join(command)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _tool_available(tool: str) -> bool:
    from shutil import which

    return which(tool) is not None


def _spore_for_risk(spores, risk):
    if risk.language in {"javascript", "typescript"}:
        name = "js-ts-timezone-boundary"
    elif risk.risk_type == "timezone_boundary":
        name = "python-timezone-boundary"
    elif risk.risk_type == "mutable_default_argument":
        name = "python-mutable-default-argument"
    elif risk.risk_type == "broad_exception_swallow":
        name = "python-broad-exception-swallow"
    else:
        return None
    return next((item for item in spores if item.name == name), None)


if __name__ == "__main__":
    app()
