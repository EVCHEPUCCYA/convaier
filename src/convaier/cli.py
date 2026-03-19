import argparse
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
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
        logging.error("Config not found: %s", config_path)
        logging.error("Run 'convaier init' to create one.")
        return 1

    config = load_config(config_path)
    stages = args.stage.split(",") if args.stage else None
    ctx = run_pipeline(config, stage_filter=stages, dry_run=args.dry_run)
    return 1 if ctx.errors else 0


def _cmd_init(args: argparse.Namespace) -> int:
    from convaier.config import generate_example_config

    target = Path(args.output)
    if target.exists() and not args.force:
        logging.error("File already exists: %s (use --force to overwrite)", target)
        return 1
    generate_example_config(target)
    logging.info("Created %s", target)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    from convaier.config import load_config

    config_path = Path(args.config)
    if not config_path.exists():
        logging.error("Config not found: %s", config_path)
        return 1

    config = load_config(config_path)
    logging.info("Config OK: %s", config_path)

    try:
        import ollama as ollama_lib

        client = ollama_lib.Client(host=config.ollama.host)
        client.list()
        logging.info("Ollama OK: %s", config.ollama.host)
    except Exception as e:
        logging.error("Ollama connection failed: %s", e)
        return 1

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

    # check
    check_p = sub.add_parser("check", help="Validate config and Ollama connectivity")
    check_p.add_argument("-c", "--config", default="convaier.yml", help="Config file path")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handlers = {"run": _cmd_run, "init": _cmd_init, "check": _cmd_check}
    sys.exit(handlers[args.command](args))
