#!/usr/bin/env python3
"""Temp-repo tests for bin/git-local-cleanup."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'bin' / 'git-local-cleanup'


def load_mod():
    loader = SourceFileLoader('git_local_cleanup', str(SCRIPT))
    spec = spec_from_loader(loader.name, loader)
    assert spec is not None
    mod = module_from_spec(spec)
    sys.modules[loader.name] = mod
    loader.exec_module(mod)
    return mod


mod = load_mod()


def git(repo: str | Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ['git', '-C', str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f'git {" ".join(args)} failed: {(result.stderr or result.stdout).strip()}'
        )
    return (result.stdout or '').strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class GitLocalCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bare = root / 'origin.git'
        self.repo = root / 'repo'
        subprocess.run(
            ['git', 'init', '--bare', '-b', 'main', str(self.bare)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ['git', 'clone', str(self.bare), str(self.repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        git(self.repo, 'config', 'user.email', 'test@example.com')
        git(self.repo, 'config', 'user.name', 'Test')
        write(self.repo / 'README', 'base\n')
        git(self.repo, 'add', 'README')
        git(self.repo, 'commit', '-m', 'initial')
        git(self.repo, 'push', '-u', 'origin', 'main')
        git(self.bare, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        self.old_cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.old_cwd)

    def commit_file(self, name: str, content: str, message: str) -> None:
        write(self.repo / name, content)
        git(self.repo, 'add', name)
        git(self.repo, 'commit', '-m', message)

    def test_detect_base_uses_origin_head(self) -> None:
        self.assertEqual(mod.detect_base(str(self.repo)), 'main')

    def test_prune_deletes_merged_branch_keeps_unmerged(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/merged')
        self.commit_file('merged.txt', 'm\n', 'merged work')
        git(self.repo, 'checkout', 'main')
        git(self.repo, 'merge', '--no-ff', 'feat/merged', '-m', 'merge feat')
        git(self.repo, 'push', 'origin', 'main')

        git(self.repo, 'checkout', '-b', 'feat/unique')
        self.commit_file('unique.txt', 'u\n', 'unique work')
        git(self.repo, 'checkout', 'main')

        info = mod.classify(str(self.repo))
        plan = mod.plan_prune(info)
        names = [
            step.data.get('name')
            for step in plan.steps
            if step.action == 'branch_delete'
        ]
        self.assertIn('feat/merged', names)
        self.assertNotIn('feat/unique', names)
        self.assertNotIn('main', names)

        mod.apply_plan(plan, dry_run=False, origin_base=info.origin_base)
        branches = git(self.repo, 'for-each-ref', '--format=%(refname:short)', 'refs/heads')
        self.assertNotIn('feat/merged', branches.splitlines())
        self.assertIn('feat/unique', branches.splitlines())
        self.assertEqual(git(self.repo, 'branch', '--show-current'), 'main')

    def test_prune_stays_on_unmerged_current_branch(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/wip')
        self.commit_file('wip.txt', 'w\n', 'wip')
        info = mod.classify(str(self.repo))
        self.assertFalse(info.current_merged)
        plan = mod.plan_prune(info)
        actions = [step.action for step in plan.steps]
        self.assertNotIn('checkout', actions)
        mod.apply_plan(plan, dry_run=False, origin_base=info.origin_base)
        self.assertEqual(git(self.repo, 'branch', '--show-current'), 'feat/wip')

    def test_prune_removes_merged_worktree_keeps_unmerged(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/merged-wt')
        self.commit_file('mw.txt', 'm\n', 'merged wt')
        git(self.repo, 'checkout', 'main')
        git(self.repo, 'merge', '--no-ff', 'feat/merged-wt', '-m', 'merge wt')
        git(self.repo, 'push', 'origin', 'main')

        git(self.repo, 'checkout', '-b', 'feat/open')
        self.commit_file('open.txt', 'o\n', 'open work')
        git(self.repo, 'checkout', 'main')

        merged_wt = Path(self.tmp.name) / 'wt-merged'
        open_wt = Path(self.tmp.name) / 'wt-open'
        git(self.repo, 'worktree', 'add', str(merged_wt), 'feat/merged-wt')
        git(self.repo, 'worktree', 'add', str(open_wt), 'feat/open')

        info = mod.classify(str(self.repo))
        plan = mod.plan_prune(info)
        removed = [
            step.data.get('path')
            for step in plan.steps
            if step.action == 'worktree_remove'
        ]
        self.assertIn(str(merged_wt), removed)
        self.assertNotIn(str(open_wt), removed)
        mod.apply_plan(plan, dry_run=False, origin_base=info.origin_base)
        self.assertFalse(merged_wt.exists())
        self.assertTrue(open_wt.exists())

    def test_prune_skips_uniquely_dirty_merged_worktree(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/dirty')
        self.commit_file('d.txt', 'd\n', 'dirty branch')
        git(self.repo, 'checkout', 'main')
        git(self.repo, 'merge', '--no-ff', 'feat/dirty', '-m', 'merge dirty')
        git(self.repo, 'push', 'origin', 'main')

        dirty_wt = Path(self.tmp.name) / 'wt-dirty'
        git(self.repo, 'worktree', 'add', str(dirty_wt), 'feat/dirty')
        write(dirty_wt / 'local.txt', 'unique dirty\n')

        info = mod.classify(str(self.repo))
        plan = mod.plan_prune(info)
        removed = [
            step.data.get('path')
            for step in plan.steps
            if step.action == 'worktree_remove'
        ]
        self.assertNotIn(str(dirty_wt), removed)
        self.assertTrue(any('uniquely dirty' in note for note in plan.notes))

    def test_prune_stashes_unique_wip_on_merged_current_branch(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/done')
        self.commit_file('done.txt', 'd\n', 'done')
        git(self.repo, 'checkout', 'main')
        git(self.repo, 'merge', '--no-ff', 'feat/done', '-m', 'merge done')
        git(self.repo, 'push', 'origin', 'main')
        git(self.repo, 'checkout', 'feat/done')
        write(self.repo / 'wip.txt', 'please keep\n')

        info = mod.classify(str(self.repo))
        self.assertTrue(info.current_merged)
        plan = mod.plan_prune(info)
        self.assertTrue(any(step.action == 'stash' for step in plan.steps))
        mod.apply_plan(plan, dry_run=False, origin_base=info.origin_base)
        self.assertEqual(git(self.repo, 'branch', '--show-current'), 'main')
        stash = git(self.repo, 'stash', 'list')
        self.assertIn('WIP leftover from feat/done', stash)
        git(self.repo, 'stash', 'pop')
        self.assertEqual((self.repo / 'wip.txt').read_text(), 'please keep\n')

    def test_only_main_backs_up_then_deletes_unmerged(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/keep-sha')
        self.commit_file('keep.txt', 'k\n', 'unique commit')
        unique_sha = git(self.repo, 'rev-parse', 'HEAD')
        git(self.repo, 'checkout', 'main')

        extra = Path(self.tmp.name) / 'wt-extra'
        git(self.repo, 'worktree', 'add', '-b', 'feat/other', str(extra), 'HEAD')
        write(extra / 'other.txt', 'other unique\n')
        git(extra, 'add', 'other.txt')
        git(extra, 'commit', '-m', 'other unique')

        info = mod.classify(str(self.repo))
        plan = mod.plan_only_main(info, timestamp='20260101T000000Z')
        backups = [step for step in plan.steps if step.action == 'backup_ref']
        deletes = [
            step.data['name']
            for step in plan.steps
            if step.action == 'branch_delete'
        ]
        self.assertTrue(any(step.data['sha'] == unique_sha for step in backups))
        self.assertIn('feat/keep-sha', deletes)
        self.assertIn('feat/other', deletes)

        mod.apply_plan(plan, dry_run=False, origin_base=info.origin_base)
        branches = git(self.repo, 'for-each-ref', '--format=%(refname:short)', 'refs/heads')
        self.assertEqual(branches.splitlines(), ['main'])
        self.assertFalse(extra.exists())
        backed = git(
            self.repo,
            'rev-parse',
            'refs/backup/local-reset/20260101T000000Z/feat/keep-sha',
        )
        self.assertEqual(backed, unique_sha)
        self.assertEqual(git(self.repo, 'branch', '--show-current'), 'main')
        stash = git(self.repo, 'stash', 'list')
        # extra worktree unique file was committed, not dirty; no stash required
        self.assertTrue(stash == '' or 'WIP leftover' in stash)

    def test_only_main_dry_run_does_not_mutate(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/stay')
        self.commit_file('stay.txt', 's\n', 'stay')
        git(self.repo, 'checkout', 'main')
        info = mod.classify(str(self.repo))
        plan = mod.plan_only_main(info, timestamp='20260101T000000Z')
        mod.apply_plan(plan, dry_run=True, origin_base=info.origin_base)
        branches = git(self.repo, 'for-each-ref', '--format=%(refname:short)', 'refs/heads')
        self.assertIn('feat/stay', branches.splitlines())
        rc, _, _ = mod.run_rc(
            ['git', 'show-ref', '--verify', '--quiet',
             'refs/backup/local-reset/20260101T000000Z/feat/stay'],
            cwd=str(self.repo),
        )
        self.assertNotEqual(rc, 0)

    def test_only_main_stashes_unique_dirty_then_removes_worktree(self) -> None:
        extra = Path(self.tmp.name) / 'wt-wip'
        git(self.repo, 'worktree', 'add', '-b', 'feat/wip-wt', str(extra), 'HEAD')
        write(extra / 'scratch.txt', 'do not drop\n')
        info = mod.classify(str(self.repo))
        plan = mod.plan_only_main(info, timestamp='20260101T000000Z')
        self.assertTrue(any(step.action == 'stash' for step in plan.steps))
        mod.apply_plan(plan, dry_run=False, origin_base=info.origin_base)
        self.assertFalse(extra.exists())
        stash = git(self.repo, 'stash', 'list')
        self.assertIn('WIP leftover from feat/wip-wt', stash)
        git(self.repo, 'stash', 'pop')
        self.assertEqual((self.repo / 'scratch.txt').read_text(), 'do not drop\n')

    def test_prune_never_plans_force_delete(self) -> None:
        git(self.repo, 'checkout', '-b', 'feat/merged')
        self.commit_file('x.txt', 'x\n', 'x')
        git(self.repo, 'checkout', 'main')
        git(self.repo, 'merge', '--no-ff', 'feat/merged', '-m', 'merge')
        git(self.repo, 'push', 'origin', 'main')
        git(self.repo, 'checkout', '-b', 'feat/open')
        self.commit_file('y.txt', 'y\n', 'y')
        git(self.repo, 'checkout', 'main')
        info = mod.classify(str(self.repo))
        plan = mod.plan_prune(info)
        for step in plan.steps:
            if step.action == 'branch_delete':
                self.assertFalse(step.data.get('force'))


if __name__ == '__main__':
    unittest.main()
