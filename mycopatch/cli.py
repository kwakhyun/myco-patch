from __future__ import annotations

from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mycopatch.core.cost import record_cost_event
from mycopatch.core.memory import append_memory_event
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
from mycopatch.core.spore_loader import load_spores
from mycopatch.core.verifier import verify_probe


app = typer.Typer(help="MycoPatch: an offline immune system for codebases.")
spores_app = typer.Typer(help="Inspect available spores.")
app.add_typer(spores_app, name="spores")
console = Console()


class HuntMode(str, Enum):
    safe = "safe"
    aggressive = "aggressive"


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
def scan() -> None:
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
            "test_files": scan_result.test_file_count,
            "risk_count": len(risks),
        },
    )
    for risk in risks:
        append_memory_event(root, "risk_detected", risk.json_dict())
    record_cost_event(
        root,
        input_text=" ".join(finding.path for finding in scan_result.python_files),
        output_text=f"repo weather report with {len(risks)} risk(s)",
        notes="repo scan and weather report",
    )
    report_path = write_repo_weather(root, scan_result, risks)
    console.print(
        f"[green]Scan complete.[/green] Python files: {scan_result.python_file_count}, "
        f"tests: {scan_result.test_file_count}, risks: {len(risks)}"
    )
    console.print(f"Report: {report_path}")


@app.command()
def hunt(
    budget: int = typer.Option(30000, help="Estimated token budget for this hunt."),
    run: bool = typer.Option(True, "--run/--no-run", help="Run generated probes with pytest."),
    mode: HuntMode = typer.Option(HuntMode.safe, help="Probe generation mode: safe or aggressive."),
) -> None:
    """Generate and optionally verify probes from loaded spores."""
    _require_initialized()
    root = Path.cwd().resolve()
    mode_value = mode.value
    scan_result = scan_repository(root)
    risks = map_timezone_risks(scan_result)
    spores = load_spores(root)
    spore = next((item for item in spores if item.name == "python-timezone-boundary"), None)

    if spore is None:
        console.print("[yellow]No timezone-boundary spore is available.[/yellow]")
        append_memory_event(root, "probe_inconclusive", {"reason": "missing timezone spore"})
        return

    if not risks:
        console.print("[yellow]No clear timezone/date-boundary target found.[/yellow]")
        append_memory_event(root, "probe_inconclusive", {"reason": "no clear target"})
        record_cost_event(root, input_text=scan_result.model_dump_json(), budget_limit=budget, notes="inconclusive hunt")
        return

    top_risk = risks[0]
    probe = generate_timezone_probe(root, top_risk, spore, mode=mode_value)
    append_memory_event(root, "probe_generated", {"probe": probe.json_dict(), "risk": top_risk.json_dict()})
    record_cost_event(
        root,
        input_text=scan_result.model_dump_json() + top_risk.model_dump_json(),
        output_text=probe.model_dump_json(),
        budget_limit=budget,
        notes=f"offline heuristic {mode_value} probe generation",
    )

    if not run:
        append_memory_event(root, "probe_inconclusive", {"probe": probe.json_dict(), "reason": "verification disabled"})
        console.print(f"[yellow]Probe generated but not run:[/yellow] {probe.path}")
        return

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
) -> None:
    """Print top risk findings without generating probes."""
    _require_initialized()
    root = Path.cwd().resolve()
    scan_result = scan_repository(root)
    findings = map_timezone_risks(scan_result)

    if not findings:
        console.print("[green]No clear timezone/date-boundary risks detected.[/green]")
        return

    table = Table(title="MycoPatch Top Risks")
    table.add_column("Score", justify="right")
    table.add_column("Confidence")
    table.add_column("Nearby Test")
    table.add_column("File")
    table.add_column("Evidence")
    for risk in findings[:limit]:
        table.add_row(
            str(risk.score),
            risk.confidence,
            "yes" if risk.nearby_test_detected else "no",
            risk.file_path,
            risk.evidence[0] if risk.evidence else "no line-level evidence",
        )
    console.print(table)


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
    _require_initialized()
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
    table = Table(title="MycoPatch Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_row(".myco initialized", "yes" if is_initialized(root) else "no")
    table.add_row("pytest available", "yes" if _pytest_available() else "no")
    table.add_row("built-in spores", str(len(load_spores(root) if is_initialized(root) else load_spores(None))))
    console.print(table)


def _require_initialized() -> None:
    if not is_initialized(Path.cwd()):
        console.print(
            "[red]MycoPatch is not initialized in the current directory.[/red]\n"
            f"Current directory: {Path.cwd()}\n"
            "Run `myco init` from the repository root, then retry this command."
        )
        raise typer.Exit(code=1)


def _pytest_available() -> bool:
    from shutil import which

    return which("pytest") is not None


if __name__ == "__main__":
    app()
