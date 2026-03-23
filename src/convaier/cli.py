import argparse
import logging
import sys
from pathlib import Path

from convaier.ui import console, print_check_fail, print_check_ok, print_presets_table


def _setup_logging(verbose: bool = False) -> None:
    if verbose:
        level = logging.DEBUG
    else:
        level = logging.ERROR
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )


def _cmd_run(args: argparse.Namespace) -> int:
    from convaier.config import load_config
    from convaier.pipeline import run_pipeline

    config_path = Path(args.config)
    if not config_path.exists():
        console.print(f"[error]Config not found: {config_path}[/]")
        console.print("[dim]Run 'convaier init' to create one.[/]")
        return 1

    config = load_config(config_path)
    stages = args.stage.split(",") if args.stage else None
    ctx = run_pipeline(config, stage_filter=stages, dry_run=args.dry_run)
    return 1 if ctx.errors else 0


def _cmd_init(args: argparse.Namespace) -> int:
    from convaier.config import generate_example_config

    target = Path(args.output)
    if target.exists() and not args.force:
        console.print(f"[error]File already exists: {target}[/] [dim](use --force to overwrite)[/]")
        return 1
    generate_example_config(target)
    console.print(f"[success]Created {target}[/]")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    from convaier.config import load_config

    config_path = Path(args.config)
    if not config_path.exists():
        console.print(f"[error]Config not found: {config_path}[/]")
        return 1

    config = load_config(config_path)

    try:
        from convaier.rag.indexer import index_project
    except ImportError:
        console.print("[error]RAG requires chromadb.[/] Install with: [bold]pip install convaier\\[rag][/]")
        return 1

    console.print(f"[dim]Indexing project: {config.project_root}[/]")

    from rich.progress import Progress
    with Progress(console=console) as progress:
        task = progress.add_task("Indexing...", total=None)
        total = index_project(config.project_root, config.ollama, force=args.force)
        progress.update(task, completed=total, total=total)

    console.print(f"[success]Done: {total} chunks indexed[/]")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    from convaier.config import load_config

    config_path = Path(args.config)
    if not config_path.exists():
        console.print(f"[error]Config not found: {config_path}[/]")
        return 1

    config = load_config(config_path)
    print_check_ok("Config", str(config_path))

    if config.language:
        print_check_ok("Language", f"{config.language} preset")

    try:
        import ollama as ollama_lib
        client = ollama_lib.Client(host=config.ollama.host)
        models = client.list()
        model_names = [m.model for m in models.models] if models.models else []
        print_check_ok("Ollama", config.ollama.host)

        if config.ollama.model in model_names:
            print_check_ok("Model", f"{config.ollama.model} (installed)")
        else:
            print_check_fail("Model", f"{config.ollama.model} (not found, run: ollama pull {config.ollama.model})")
            return 1
    except Exception as e:
        print_check_fail("Ollama", str(e))
        return 1

    console.print()
    console.print("[success]All checks passed[/]")
    return 0


def _cmd_presets(args: argparse.Namespace) -> int:
    from convaier.presets import PRESETS, list_presets

    filtered = {k: PRESETS[k] for k in list_presets()}
    print_presets_table(filtered)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="convaier",
        description="Local AI-powered CI/CD pipeline",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="Run pipeline")
    run_p.add_argument("-c", "--config", default="convaier.yml", help="Config file path")
    run_p.add_argument("-s", "--stage", help="Comma-separated stage names to run")
    run_p.add_argument("--dry-run", action="store_true", help="Show stages without running")

    # init
    init_p = sub.add_parser("init", help="Generate example config")
    init_p.add_argument("-o", "--output", default="convaier.yml", help="Output file path")
    init_p.add_argument("-f", "--force", action="store_true", help="Overwrite existing file")

    # index
    index_p = sub.add_parser("index", help="Index project for RAG context")
    index_p.add_argument("-c", "--config", default="convaier.yml", help="Config file path")
    index_p.add_argument("-f", "--force", action="store_true", help="Re-index from scratch")

    # presets
    sub.add_parser("presets", help="List available language presets")

    # check
    check_p = sub.add_parser("check", help="Validate config and Ollama connectivity")
    check_p.add_argument("-c", "--config", default="convaier.yml", help="Config file path")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "run": _cmd_run, "init": _cmd_init, "index": _cmd_index,
        "presets": _cmd_presets, "check": _cmd_check,
    }
    sys.exit(handlers[args.command](args))
