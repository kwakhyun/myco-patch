from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mycopatch.core.config import load_config
from mycopatch.core.cost import record_cost_event
from mycopatch.core.memory import append_memory_event
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
from mycopatch.core.risk_mapper import map_timezone_risks
from mycopatch.core.spore_loader import load_builtin_spores, load_spores
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
        console.print(f"[green]MycoPatch already initialized; verified layout at[/green] {paths.myco}")
        return

    append_memory_event(
        paths.repo_root,
        "repo_initialized",
        {"myco_dir": paths.myco.relative_to(paths.repo_root).as_posix()},
    )
    console.print(f"[green]Initialized MycoPatch at[/green] {paths.myco}")


@app.command()
def scan(
    json_output: bool = typer.Option(False, "--json", help="Print a machine-readable JSON summary."),
) -> None:
    """Scan the repository and write a repo weather report."""
    _require_initialized()
    root = Path.cwd().resolve()
    scan_result = scan_repository(root)
    risks = map_timezone_risks(scan_result)
    append_memory_event(
        root,
        "scan_completed",
        {
            "python_files": scan_result.python_file_count,
            "js_ts_files": scan_result.js_ts_file_count,
            "test_files": scan_result.test_file_count,
            "risk_count": len(risks),
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
        f"JS/TS files: {scan_result.js_ts_file_count}, tests: {scan_result.test_file_count}, risks: {len(risks)}"
    )
    console.print(f"Report: {report_path}")


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
    risks = map_timezone_risks(scan_result)
    spores = load_spores(root)

    if not risks:
        console.print("[yellow]No clear timezone/date-boundary target found.[/yellow]")
        append_memory_event(root, "probe_inconclusive", {"reason": "no clear target"})
        record_cost_event(root, input_text=scan_result.model_dump_json(), budget_limit=budget, notes="inconclusive hunt")
        return

    matching_risks = _filter_risks(risks, language, target_file)
    selected_risks = matching_risks if all_risks else matching_risks[:limit]
    if not selected_risks:
        console.print("[yellow]No timezone/date-boundary risks matched the requested filters.[/yellow]")
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
            console.print(f"[yellow]No timezone-boundary spore is available for {risk.language}.[/yellow]")
            append_memory_event(root, "probe_inconclusive", {"reason": f"missing timezone spore for {risk.language}"})
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
    findings = map_timezone_risks(scan_result)
    selected = findings[:limit]

    if not findings:
        if json_output:
            typer.echo("[]")
            return
        console.print("[green]No clear timezone/date-boundary risks detected.[/green]")
        return

    if json_output:
        typer.echo(json.dumps([risk.json_dict() for risk in selected], sort_keys=True))
        return

    _print_risk_table(selected)


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
    console.print(f"Report: {paths.patch_recommendations}")


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
    table.add_row("pytest available", "yes" if _pytest_available() else "no")
    table.add_row("node available", "yes" if _node_available() else "no")
    table.add_row("built-in spores", str(len(builtin_spores)))
    table.add_row("local spores", str(len(local_spores)))
    table.add_row("config valid", "yes" if config_error is None else f"no: {config_error}")
    if config is not None:
        table.add_row("provider", config.default_provider)
        table.add_row("provider network", "enabled" if config.allow_network_for_model_provider else "disabled")
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


def _scan_json_payload(
    scan_result: RepoScanResult,
    risks: list[RiskFinding],
    report_path: Path,
) -> dict:
    return {
        "repo_path": ".",
        "python_files": scan_result.python_file_count,
        "js_ts_files": scan_result.js_ts_file_count,
        "test_files": scan_result.test_file_count,
        "framework_hints": scan_result.framework_hints,
        "risk_count": len(risks),
        "top_risks": [risk.json_dict() for risk in risks[:10]],
        "report_path": report_path.relative_to(Path.cwd().resolve()).as_posix(),
    }


def _pytest_available() -> bool:
    from shutil import which

    return which("pytest") is not None


def _node_available() -> bool:
    from shutil import which

    return which("node") is not None


def _spore_for_risk(spores, risk):
    if risk.language == "python":
        name = "python-timezone-boundary"
    else:
        name = "js-ts-timezone-boundary"
    return next((item for item in spores if item.name == name), None)


if __name__ == "__main__":
    app()
