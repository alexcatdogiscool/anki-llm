import os
import git_utils
from aqt.utils import tooltip


# cloud sync stuff

addon_dir = os.path.dirname(__file__)
DATABASE_PATH = os.path.join(addon_dir, "db", "database.txt")
REPO_PATH = os.path.join(addon_dir, "db")



repo_ready = False

def init_repo():
    global repo_ready
    if not git_utils.is_git_repo(REPO_PATH):
        print(f"[llm-addon] {REPO_PATH} is not a git repo, sync disabled")
        return
 
    try:
        git_utils.pull(REPO_PATH)
        repo_ready = True
    except git_utils.GitError as e:
        # Don't crash addon load just because we couldn't pull (e.g. offline).
        # We can still use the local DB as-is.
        print(f"[llm-addon] pull failed, continuing with local db: {e}")
        repo_ready = True
 
 
def sync_cloud():
    if not repo_ready:
        return
 
    try:
        git_utils.add_all(REPO_PATH)
        if git_utils.has_changes(REPO_PATH):
            git_utils.commit(REPO_PATH, "changes updates")
            git_utils.push(REPO_PATH)
            print("[llm-addon] pushed successfully")
        else:
            print("[llm-addon] nothing to push")
    except git_utils.GitError as e:
        print(f"[llm-addon] sync failed: {e}")
        tooltip(f"llm-addon: cloud sync failed ({e})")

## db stuff

init_repo()

with open(DATABASE_PATH, "a") as f:
    f.write("\nauto sync!!\n")
f.close()



sync_cloud()