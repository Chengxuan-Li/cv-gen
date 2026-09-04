"""Structured diagnostics.

Every problem carries a stable `code` alongside its prose message. Agents branch
on the code; humans read the message. Rewording a message is therefore safe,
while changing or removing a code is a breaking change - treat `CODES` as the
published contract.

Problems also carry a source line where one can be recovered. The line index is
built by composing the YAML into a node tree and walking it, rather than by
injecting markers into the parsed data, so nothing leaks into the content model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# The published diagnostic contract. Grouped by what an agent would do about it.
CODES = (
    # File-level
    "file_not_found",
    "invalid_yaml",
    "empty_file",
    "not_a_mapping",
    # Section structure
    "unknown_block_type",
    "item_not_a_mapping",
    "missing_required_field",
    "invalid_field_type",
    # Markers
    "malformed_marker",
    "undeclared_variant",
    # Cross-file wiring
    "missing_section_file",
    "no_sections_listed",
    "no_documents_declared",
    "legacy_yml_extension",
    # Selection, raised at build time rather than load time
    "no_surviving_tagline",
    "unknown_document",
    # Lint, warnings rather than errors
    "near_miss_marker",
    "real_contact_in_tracked_profile",
)


def format_path(parts: tuple[object, ...]) -> str:
    """('entries', 0, 'org') -> 'entries[0].org'"""
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


@dataclass(frozen=True)
class Problem:
    file: str
    code: str
    message: str
    line: int | None = None
    path: str = ""
    field: str = ""
    hint: str = ""

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict:
        out = {"file": self.file, "code": self.code, "message": self.message}
        if self.line is not None:
            out["line"] = self.line
        for key in ("path", "field", "hint"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


def line_index(text: str) -> dict[tuple, int]:
    """Map each YAML path tuple to its 1-based source line.

    Composing to a node tree keeps this out of the parsed data - the alternative,
    stashing a `__line__` key during construction, pollutes every mapping and
    leaks into anything that iterates keys.
    """
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return {}
    if root is None:
        return {}

    index: dict[tuple, int] = {}

    def walk(node: yaml.Node, path: tuple) -> None:
        index[path] = node.start_mark.line + 1
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                index[path + (key.value,)] = key.start_mark.line + 1
                walk(value, path + (key.value,))
        elif isinstance(node, yaml.SequenceNode):
            for i, value in enumerate(node.value):
                walk(value, path + (i,))

    walk(root, ())
    return index


@dataclass
class Source:
    """One YAML file: its parsed data plus a path-to-line index."""

    path: Path
    data: dict
    lines: dict[tuple, int]

    @property
    def name(self) -> str:
        return self.path.name

    def line_at(self, path: tuple) -> int | None:
        return self.lines.get(tuple(path))

    def problem(
        self,
        code: str,
        message: str,
        path: tuple = (),
        field: str = "",
        hint: str = "",
    ) -> Problem:
        """Build a Problem anchored to this file, prefixing the message with it."""
        return Problem(
            file=self.name,
            code=code,
            message=f"{self.name}: {message}",
            line=self.line_at(path),
            path=format_path(path),
            field=field,
            hint=hint,
        )
