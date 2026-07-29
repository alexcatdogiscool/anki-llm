import os
import subprocess


def _in_flatpak_sandbox() -> bool:
    return os.path.exists("/.flatpak-info")


def _git_base_cmd():
    if _in_flatpak_sandbox():
        return ["flatpak-spawn", "--host", "git"]
    return ["git"]


class GitError(Exception):
    pass


def run_git(*args, cwd, timeout=30):
    """Run a git command in `cwd`, returning stdout. Raises GitError on failure."""
    cmd = _git_base_cmd() + list(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise GitError(
            "git executable not found. Is git installed on your system "
            "(and on your host, if running Anki via Flatpak)?"
        )
    except subprocess.TimeoutExpired:
        raise GitError(f"git {' '.join(args)} timed out after {timeout}s")

    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed:\n{result.stderr.strip()}"
        )

    return result.stdout.strip()


def is_git_repo(path) -> bool:
    if not os.path.isdir(os.path.join(path, ".git")):
        return False
    try:
        run_git("rev-parse", "--is-inside-work-tree", cwd=path)
        return True
    except GitError:
        return False


def pull(path):
    return run_git("pull", cwd=path)


def add_all(path):
    return run_git("add", "-A", cwd=path)


def has_changes(path) -> bool:
    status = run_git("status", "--porcelain", cwd=path)
    return bool(status)


def commit(path, message):
    return run_git("commit", "-m", message, cwd=path)


def push(path):
    return run_git("push", cwd=path)