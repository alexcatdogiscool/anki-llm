
from aqt import gui_hooks
from anki.cards import Card
from anki import hooks
from anki.template import TemplateRenderContext, TemplateRenderOutput
from aqt.utils import tooltip
import sqlite3
from git import Repo
import os
from . import git_utils


# cloud sync stuff

addon_dir = os.path.dirname(__file__)
DATABASE_PATH = os.path.join(addon_dir, "db", "sentences.db")
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

conn = sqlite3.connect(DATABASE_PATH)
cur = conn.cursor()


def get_db_entries(word):
    cur.execute(
        "SELECT * FROM sentences WHERE word = ? AND dirty = 0", (word,)
    )

    result = cur.fetchall()

    if len(result) != 0:
        return result

    # were here if there are no clean entries

    # get dirty entries
    cur.execute(
        "SELECT * FROM sentences WHERE word = ? AND dirty = 1", (word,)
    )

    result = cur.fetchall()

    if len(result) != 0:
        return result

    #we are here if there are no results at all??

    return None

def select_and_dirty(options: list) -> tuple:
    entry = options[0]

    cur.execute(
        "UPDATE sentences SET dirty = 1 WHERE id = ?",
        (entry[0],)
    )

    conn.commit()

    return entry

def add_html_from_mark(sentence: str):
    return sentence.replace("{{", "<mark>").replace("}}", "</mark>")

def render_new(
        output: TemplateRenderOutput, context: TemplateRenderContext
) -> None:

    results = get_db_entries(output.question_text)

    if results == None:
        # dont change the card. weve got nothinf to add
        return

    result = select_and_dirty(results)

    question = add_html_from_mark(result[3])

    # set the new question
    output.question_text = question

    # work on answer

    answer = ""
    answer += "Word: " + result[1] + "<br>"
    answer += "Chinese: " + question + "<br>"
    answer += "Pinyin: " + result[4] + "<br>"
    answer += "English: " + result[5]

    output.answer_text = answer



def sync_cloud():
    commit_changes(repo)
    push_to_origin(repo)



hooks.card_did_render.append(render_new)

gui_hooks.reviewer_will_end(sync_cloud)

