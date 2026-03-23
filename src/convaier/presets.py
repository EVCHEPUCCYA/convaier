"""Built-in language presets for pipeline stages."""
from __future__ import annotations

PRESETS: dict[str, dict] = {
    "python": {
        "lint": {
            "tools": [
                {"command": "python -m ruff check .", "name": "ruff"},
            ],
        },
        "security": {
            "tools": [
                {"command": "python -m bandit -r . -f json --quiet", "name": "bandit"},
                {"command": "python -m pip_audit --format=json", "name": "pip-audit"},
            ],
        },
        "metrics": {
            "src_path": ".",
        },
        "test": {
            "command": "python -m pytest --tb=short -q",
        },
    },

    "javascript": {
        "lint": {
            "tools": [
                {"command": "npx eslint . --format json", "name": "eslint"},
            ],
        },
        "security": {
            "tools": [
                {"command": "npm audit --json", "name": "npm-audit"},
            ],
        },
        "test": {
            "command": "npm test",
        },
    },

    "typescript": {
        "lint": {
            "tools": [
                {"command": "npx eslint . --format json", "name": "eslint"},
                {"command": "npx tsc --noEmit", "name": "tsc"},
            ],
        },
        "security": {
            "tools": [
                {"command": "npm audit --json", "name": "npm-audit"},
            ],
        },
        "test": {
            "command": "npm test",
        },
    },

    "java": {
        "lint": {
            "tools": [
                {"command": "mvn checkstyle:check -q", "name": "checkstyle"},
            ],
        },
        "security": {
            "tools": [
                {"command": "mvn org.owasp:dependency-check-maven:check -q", "name": "dependency-check"},
            ],
        },
        "test": {
            "command": "mvn test -q",
        },
    },

    "go": {
        "lint": {
            "tools": [
                {"command": "golangci-lint run --out-format json", "name": "golangci-lint"},
            ],
        },
        "security": {
            "tools": [
                {"command": "gosec -fmt=json ./...", "name": "gosec"},
                {"command": "govulncheck ./...", "name": "govulncheck"},
            ],
        },
        "test": {
            "command": "go test ./... -v",
        },
    },
}

# Aliases
PRESETS["js"] = PRESETS["javascript"]
PRESETS["ts"] = PRESETS["typescript"]


def get_preset(language: str) -> dict | None:
    """Get preset by language name (case-insensitive)."""
    return PRESETS.get(language.lower())


def list_presets() -> list[str]:
    """List available preset names (without aliases)."""
    return [k for k in PRESETS if k not in ("js", "ts")]


def apply_preset(language: str, stages_config: dict) -> dict:
    """Merge preset defaults with user overrides.

    User config takes priority — preset only fills in missing values.
    """
    preset = get_preset(language)
    if not preset:
        return stages_config

    merged = dict(stages_config)
    for stage_name, stage_defaults in preset.items():
        if stage_name not in merged:
            merged[stage_name] = stage_defaults
        else:
            # User has this stage — only fill missing keys
            for key, value in stage_defaults.items():
                if key not in merged[stage_name]:
                    merged[stage_name][key] = value

    return merged
