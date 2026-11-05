# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from collections.abc import Collection
from logging import Logger, getLogger

from opentelemetry.util._importlib_metadata import (
    Distribution,
    PackageNotFoundError,
    version,
)

_logger = getLogger(__name__)
_PACKAGE_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_VERSION_PREFIX_RE = re.compile(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", re.IGNORECASE)
_SPEC_RE = re.compile(r"(~=|==|!=|<=|>=|<|>)\s*([^\s,;]+)")
_EXTRA_RE = re.compile(r"""\bextra\s*==\s*['"]([^'"]+)['"]""")


def _parse_version_tuple(version_str: str) -> tuple[int, int, int] | None:
    """Extract the (major, minor, patch) prefix from a version string, dropping any suffix."""
    match = _VERSION_PREFIX_RE.match(version_str)
    if not match:
        return None
    major, minor, patch = match.groups(default="0")
    return (int(major), int(minor), int(patch))


def _matches_specifiers(installed_version_str: str, spec_str: str) -> bool:
    """Check whether installed_version_str satisfies all comma-separated version specifiers in spec_str."""
    if not spec_str.strip():
        return True
    installed = _parse_version_tuple(installed_version_str)
    if installed is None:
        return False
    for op, target_str in _SPEC_RE.findall(spec_str):
        match = _VERSION_PREFIX_RE.match(target_str)
        if not match:
            return False
        major, minor, patch = match.groups(default="0")
        target = (int(major), int(minor), int(patch))
        if op == ">=" and installed < target:
            return False
        if op == "<=" and installed > target:
            return False
        if op == ">" and installed <= target:
            return False
        if op == "<" and installed >= target:
            return False
        if op == "==" and installed != target:
            return False
        if op == "!=" and installed == target:
            return False
        if op == "~=":
            if match.group(2) is None:
                return False
            upper = (target[0] + 1, 0, 0) if match.group(3) is None else (target[0], target[1] + 1, 0)
            if not (installed >= target and installed < upper):
                return False
    return True


def _parse_dependency(dep: str) -> tuple[str, str, str]:
    """Parse a requirement string into (package_name, specifier_part, normalized_display_str)."""
    req_part, sep, marker_part = dep.partition(";")
    match = _PACKAGE_NAME_RE.match(req_part)
    if not match:
        raise ValueError(f"Invalid dependency requirement: {dep!r}")
    name = match.group(1)
    spec_part = req_part[match.end() :].strip()
    # Validate that any trailing text after the package name consists of valid specifiers
    if spec_part:
        cleaned = _SPEC_RE.sub("", spec_part).replace(",", "").strip()
        if cleaned:
            raise ValueError(f"Invalid specifier in requirement: {dep!r}")
    norm_spec = ",".join(f"{op}{ver}" for op, ver in _SPEC_RE.findall(spec_part))
    norm_str = f"{name}{norm_spec}"
    if sep:
        norm_str = f"{norm_str}; {marker_part.strip()}"
    return name, spec_part, norm_str


def _format_deps(deps: Collection[str]) -> str:
    return ", ".join(str(dep) for dep in deps)


class DependencyConflict:
    """Represents a dependency conflict in OpenTelemetry instrumentation.

    This class is used to track conflicts between required dependencies and the
    actual installed packages. It supports two scenarios:

    1. Standard conflicts where all dependencies are required
    2. Either/or conflicts where only one of a set of dependencies is required

    Attributes:
        required: The required dependency specification that conflicts with what's installed.
        found: The actual dependency that was found installed (if any).
        required_any: Collection of dependency specifications where any one would satisfy
            the requirement (for either/or scenarios).
        found_any: Collection of actual dependencies found for either/or scenarios.
    """

    required: str | None = None
    found: str | None = None
    # The following fields are used when an instrumentation requires any of a set of dependencies rather than all.
    required_any: Collection[str] = None
    found_any: Collection[str] = None

    def __init__(
        self,
        required: str | None = None,
        found: str | None = None,
        required_any: Collection[str] = None,
        found_any: Collection[str] = None,
    ):
        self.required = required
        self.found = found
        # The following fields are used when an instrumentation requires any of a set of dependencies rather than all.
        self.required_any = required_any
        self.found_any = found_any

    @property
    def _is_version_conflict(self) -> bool:
        """False when the dependency is not installed at all, rather than installed at an incompatible version."""
        return bool(self.found or self.found_any)

    def _log(self, logger: Logger, instrumentor_name: str) -> None:
        """Log as an error for a version conflict, at debug level when the dependency is not installed."""
        log = logger.error if self._is_version_conflict else logger.debug
        log(self._format_message(instrumentor_name))

    def _format_message(self, instrumentor_name: str | None = None) -> str:
        subject = instrumentor_name or "This instrumentation"
        if self.required:
            if self.found:
                return (
                    f'{subject} only instruments "{self.required}", '
                    f'but currently installed version ("{self.found}") falls outside of that range, '
                    f"so nothing can be instrumented."
                )
            return (
                f'{subject} only instruments "{self.required}", '
                f"but no installed version was found, so nothing can be instrumented."
            )
        if self.required_any:
            if self.found_any:
                return (
                    f'{subject} instruments any of "{_format_deps(self.required_any)}", '
                    f'but currently installed version(s) ("{_format_deps(self.found_any)}") fall outside of that range, '
                    f"so nothing can be instrumented."
                )
            return (
                f'{subject} requires any of "{_format_deps(self.required_any)}", '
                f"but none are installed, so nothing can be instrumented."
            )
        return f"{subject} has an unknown dependency conflict, so nothing can be instrumented."

    def __str__(self):
        return self._format_message()


class DependencyConflictError(Exception):
    conflict: DependencyConflict

    def __init__(self, conflict: DependencyConflict):
        self.conflict = conflict

    def __str__(self):
        return str(self.conflict)


def get_dist_dependency_conflicts(
    dist: Distribution,
) -> DependencyConflict | None:
    instrumentation_deps: list[str] = []
    instrumentation_any_deps: list[str] = []
    extra = "extra"
    instruments = "instruments"
    instruments_any = "instruments-any"
    if dist.requires:
        for dep in dist.requires:
            if extra not in dep:
                continue
            if instruments not in dep and instruments_any not in dep:
                continue
            _, _, marker = dep.partition(";")
            extras = _EXTRA_RE.findall(marker)
            try:
                _, _, norm_dep = _parse_dependency(dep)
            except ValueError as exc:
                _logger.warning(
                    'error parsing dependency, reporting as a conflict: "%s" - %s',
                    dep,
                    exc,
                )
                return DependencyConflict(dep)
            if instruments in extras:
                instrumentation_deps.append(norm_dep)
            if instruments_any in extras:
                instrumentation_any_deps.append(norm_dep)
    return get_dependency_conflicts(instrumentation_deps, instrumentation_any_deps)


def get_dependency_conflicts(
    deps: Collection[str],  # Dependencies all of which are required
    deps_any: Collection[str] | None = None,  # Dependencies any of which are required
) -> DependencyConflict | None:
    for dep in deps:
        dep_str = str(dep)
        try:
            pkg_name, spec_part, _ = _parse_dependency(dep_str)
        except ValueError as exc:
            _logger.warning(
                'error parsing dependency, reporting as a conflict: "%s" - %s',
                dep,
                exc,
            )
            return DependencyConflict(dep_str)

        try:
            dist_version = version(pkg_name)
        except PackageNotFoundError:
            return DependencyConflict(dep_str)

        if not _matches_specifiers(dist_version, spec_part):
            return DependencyConflict(dep_str, f"{pkg_name} {dist_version}")

    # If all the dependencies in "instruments" are present, check "instruments-any" for conflicts.
    if deps_any:
        return _get_dependency_conflicts_any(deps_any)
    return None


# This is a helper functions designed to ease reading and meet linting requirements.
def _get_dependency_conflicts_any(
    deps_any: Collection[str],
) -> DependencyConflict | None:
    if not deps_any:
        return None
    is_dependency_conflict = True
    required_any: Collection[str] = []
    found_any: Collection[str] = []
    for dep in deps_any:
        dep_str = str(dep)
        try:
            pkg_name, spec_part, _ = _parse_dependency(dep_str)
        except ValueError as exc:
            _logger.warning(
                'error parsing dependency, reporting as a conflict: "%s" - %s',
                dep,
                exc,
            )
            return DependencyConflict(dep_str)

        try:
            dist_version = version(pkg_name)
        except PackageNotFoundError:
            required_any.append(dep_str)
            continue

        if _matches_specifiers(dist_version, spec_part):
            # Since only one of the instrumentation_any dependencies is required, there is no dependency conflict.
            is_dependency_conflict = False
            break
        # If the version does not match, add it to the list of unfulfilled requirement options.
        required_any.append(dep_str)
        found_any.append(f"{pkg_name} {dist_version}")

    if is_dependency_conflict:
        return DependencyConflict(
            required_any=required_any,
            found_any=found_any,
        )
    return None
