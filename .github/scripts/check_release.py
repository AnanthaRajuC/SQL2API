#!/usr/bin/env python3
"""Refuse to publish a release unless the pushed tag is consistent with the repository.

Run by the Release workflow before anything is built or uploaded:

    python .github/scripts/check_release.py v0.2.0

It fails when
  * the tag is not `v<queryapigate.__version__>` - i.e. the tag was pushed on a commit without the version bump,
  * the tagged commit is not part of origin/main - i.e. the tag was pushed before its pull request was merged,
  * CHANGELOG.md has no dated section for the version.
"""
import re
import subprocess
import sys
from pathlib import Path


def package_version(root):
    text = (root / 'queryapigate' / '__init__.py').read_text()
    match = re.search(r'''^__version__\s*=\s*['"]([^'"]+)['"]''', text, re.M)
    if not match:
        raise SystemExit('Could not find __version__ in queryapigate/__init__.py')
    return match.group(1)


def problems(tag, root, main_ref='origin/main'):
    """Return a list of human-readable reasons the release must not go ahead (empty when it is fine)."""
    found = []
    version = package_version(root)
    if tag != f'v{version}':
        found.append(f'Tag {tag} does not match the package version {version} (expected v{version}). '
                     'The tag was probably pushed on a commit that does not contain the version bump.')

    on_main = subprocess.run(['git', 'merge-base', '--is-ancestor', 'HEAD', main_ref], cwd=root,
                             capture_output=True).returncode == 0
    if not on_main:
        found.append(f'The tagged commit is not on {main_ref}. Merge the release pull request first, '
                     'then tag the merged commit.')

    changelog = root / 'CHANGELOG.md'
    if not changelog.exists() or not re.search(rf'^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}',
                                                changelog.read_text(), re.M):
        found.append(f'CHANGELOG.md has no dated "## [{version}] - YYYY-MM-DD" section.')
    return found


def main(argv):
    if len(argv) != 2:
        raise SystemExit(f'usage: {argv[0]} <tag>')
    reasons = problems(argv[1], Path.cwd())
    for reason in reasons:
        print(f'::error::{reason}')
    if reasons:
        return 1
    print(f'Release check passed for {argv[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
