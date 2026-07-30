from ollama import generate
import sqlite3
from db import init_db, replenish, purge_dirty, init_repo, pull_latest, commit_changes, push_to_origin
import json
import postproc
from pydantic import BaseModel
import git_utils
import os

REPO_PATH = os.path.join(".", "db")
repo_ready = False

PROMPT_PATH = "/home/alex/Desktop/programming/anki-plugin/llm/prompt.txt"
ANKI_PATH = "/home/alex/.var/app/net.ankiweb.Anki/data/Anki2/User 1/collection.anki2"
FAILED_LOG_PATH = "/home/alex/Desktop/programming/anki-plugin/llm/failed_words.json"
DECK_ID = 1783246160167
MODEL = "qwen3:14b"

class Sentence(BaseModel):
    sentence: str
    pinyin: str
    gloss: str
    
class SentenceList(BaseModel):
    sentences: list[Sentence]



def unload_model():
    # explicit unload: keep_alive=0 tells Ollama to drop it from memory immediately
    generate(model=MODEL, prompt="", keep_alive=0)

def generate_sentences(prompt, keep_alive=-1):
    response = generate(
        model=MODEL,
        prompt=prompt,
        keep_alive=keep_alive,
        format=SentenceList.model_json_schema(),
        think=True,
    )
    return response.response

def lapse_rate(c):
    return c["lapses"] / c["reps"] if c["reps"] > 0 else 0

def get_known_words():
    conn = sqlite3.connect(ANKI_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT n.flds, c.ivl, c.factor, c.reps, c.lapses, c.type
        FROM cards c
        JOIN notes n ON n.id = c.nid
        WHERE c.did = ?
    """, (DECK_ID,))

    rows = cur.fetchall()
    conn.close()

    cards = []
    for r in rows:
        fields = r["flds"].split("\x1f")
        front, back = fields[0], fields[1]
        cards.append({
            "chinese": front,
            "english": back,
            "interval": r["ivl"],
            "ease": r["factor"],
            "reps": r["reps"],
            "lapses": r['lapses'],
            "state": r["type"],
        })

    consolidated = [
        c for c in cards
        if c["state"] == 2
        and c["interval"] >= 7
        and lapse_rate(c) <= 0.3
    ]

    return (cards, consolidated)


    


def generate_prompt(character, known_list, num = 1):
    p = ""
    with open(PROMPT_PATH) as f:
        p = f.read()

    known = ""
    for w in known_list:
        known += f"{w}\n"

    p = p.replace("{target}", character) \
        .replace("{n}", str(num)) \
        .replace("{known_word_list}", known)

    return p

def save_failed_log(failed_words):
    with open(FAILED_LOG_PATH, "w") as f:
        json.dump(failed_words, f, ensure_ascii=False, indent=2)


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

if __name__ == "__main__":


    ## cloud sync
    init_repo()    
    
    # sql db

    init_db()
    

    

    (all_words_dict, consolidated_dict) = get_known_words()
    all_words = []
    for c in all_words_dict:
        all_words.append(c["chinese"])

    print(all_words[:3])
    
    consolidated = []
    for c in consolidated_dict:
        consolidated.append(c["chinese"] + " - " + c["english"].split(" - ")[0])



    

    def generate_fn(word, n, max_retries=3):
        for attempt in range(1, max_retries+1):
            prompt = generate_prompt(word, consolidated, n)
            #print(prompt)
            raw = generate_sentences(prompt)
            print(raw)
            try:
                parsed = SentenceList.model_validate_json(raw)
            except Exception as e:
                print(f"  [{word}] attempt {attempt}/{max_retries}: schema validation failed: {e}")
                print(f"    raw: {raw[:200]!r}")
                continue

            sentence_dicts = [s.model_dump() for s in parsed.sentences]
            return postproc.postprocess(word, sentence_dicts)
        
        raise RuntimeError(f"'{word}': failed to get valid JSON after {max_retries} attempts")

    failed_words = []

    try:
        for word in all_words:
            try:
                added = replenish(word, generate_fn, target_pool_size=5)
                print(f"{word}: added {added} sentence(s)")
            except Exception as e:
                print(f"skipping '{word}' after failure: {e}")
                failed_words.appned(word)
                continue
    finally:
        unload_model()
        
    if failed_words:
        save_failed_log(failed_words)

    # sync to cloud
    sync_cloud()
    