#!/usr/bin/env python3
"""
Version bumping utility for aynse.

This script updates the version in pyproject.toml (single source of truth).
The version in __init__.py is read dynamically from package metadata.

Usage:
    python scripts/bump_version.py [major|minor|patch] [--dry-run]
    python scripts/bump_version.py --set 1.2.3 [--dry-run]
    
Examples:
    python scripts/bump_version.py patch        # 1.1.0 -> 1.1.1
    python scripts/bump_version.py minor        # 1.1.0 -> 1.2.0  
    python scripts/bump_version.py major        # 1.1.0 -> 2.0.0
    python scripts/bump_version.py --set 2.0.0  # Set exact version
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def read_current_version(pyproject_path: Path) -> str:
    """Read the current version from pyproject.toml."""
    content = pyproject_path.read_text(encoding='utf-8')
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a semantic version string into (major, minor, patch)."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(current: str, bump_type: str) -> str:
    """Bump the version according to bump_type."""
    major, minor, patch = parse_version(current)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


def update_pyproject(pyproject_path: Path, old_version: str, new_version: str) -> None:
    """Update version in pyproject.toml."""
    content = pyproject_path.read_text(encoding='utf-8')
    new_content = re.sub(
        r'^(version\s*=\s*["\'])' + re.escape(old_version) + r'(["\'])',
        rf'\g<1>{new_version}\g<2>',
        content,
        flags=re.MULTILINE
    )
    pyproject_path.write_text(new_content, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump the version of aynse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=["major", "minor", "patch"],
        help="Type of version bump"
    )
    parser.add_argument(
        "--set",
        dest="set_version",
        help="Set an exact version (e.g., 2.0.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Just print the current version and exit"
    )
    
    args = parser.parse_args()
    
    root = get_project_root()
    pyproject_path = root / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found", file=sys.stderr)
        return 1
    
    current_version = read_current_version(pyproject_path)
    
    if args.current:
        print(current_version)
        return 0
    
    if args.set_version:
        # Validate the version format
        try:
            parse_version(args.set_version)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        new_version = args.set_version
    elif args.bump_type:
        new_version = bump_version(current_version, args.bump_type)
    else:
        parser.print_help()
        return 1
    
    print(f"Current version: {current_version}")
    print(f"New version:     {new_version}")
    
    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return 0
    
    # Update pyproject.toml
    update_pyproject(pyproject_path, current_version, new_version)
    print(f"\n✓ Updated pyproject.toml")
    
    print(f"\nVersion bumped from {current_version} to {new_version}")
    print("\nNext steps:")
    print(f"  1. Commit: git commit -am 'Bump version to {new_version}'")
    print(f"  2. Tag:    git tag v{new_version}")
    print(f"  3. Push:   git push && git push --tags")
    print(f"  4. Create a GitHub release to trigger PyPI publish")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

