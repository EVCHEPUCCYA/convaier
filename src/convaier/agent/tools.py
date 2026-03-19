from __future__ import annotations

from pathlib import Path

REVIEW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file in the project",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to project root",
                    }
                },
                "required": ["directory"],
            },
        },
    },
]

MAX_FILE_SIZE = 10_000  # characters


def execute_tool(name: str, args: dict, project_root: Path) -> str:
    root = project_root.resolve()

    if name == "read_file":
        target = (root / args.get("path", "")).resolve()
        if not str(target).startswith(str(root)):
            return "Error: path outside project root"
        if not target.is_file():
            return f"Error: file not found: {args.get('path')}"
        content = target.read_text(errors="replace")
        if len(content) > MAX_FILE_SIZE:
            content = content[:MAX_FILE_SIZE] + f"\n... (truncated at {MAX_FILE_SIZE} chars)"
        return content

    if name == "list_files":
        target = (root / args.get("directory", "")).resolve()
        if not str(target).startswith(str(root)):
            return "Error: path outside project root"
        if not target.is_dir():
            return f"Error: directory not found: {args.get('directory')}"
        entries = sorted(target.iterdir())
        lines = []
        for e in entries[:100]:
            prefix = "[DIR] " if e.is_dir() else "      "
            lines.append(f"{prefix}{e.name}")
        return "\n".join(lines) if lines else "(empty directory)"

    return f"Unknown tool: {name}"
