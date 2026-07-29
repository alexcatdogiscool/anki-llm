import sqlite3
import random
from contextlib import contextmanager

DB_PATH = "/home/alex/Desktop/programming/anki-plugin/llm/sentences.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    sentence TEXT NOT NULL,
    sentence_marked TEXT NOT NULL,
    pinyin TEXT,
    gloss TEXT,
    dirty INTEGER NOT NULL DEFAULT 0,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_word ON sentences(word);
CREATE INDEX IF NOT EXISTS idx_word_dirty ON sentences(word, dirty);
"""

@contextmanager
def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_key = ON")
    try:
        yield conn
    finally:
        conn.close()

def init_db(db_path=DB_PATH):
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


## plugin side

def get_sentence_from_word(word, db_path=DB_PATH):
    """
    return a dict {id, sentence, pinyin, gloss} for the given word or None
    """
    with get_conn(db_path) as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT id, sentence, pinyin, gloss FROM sentences WHERE word = ? AND dirty = 0",
            (word,),
        )
        rows = cur.fetchall()

        if not rows:
            cur.execute(
                "SELECT id, sentence, pinyin, gloss FROM sentences WHERE word = ?",
                (word,),
            )
            rows = cur.fetchall()

        if not rows:
            return None

        row = random.choice(rows)

        cur.execute("UPDATE sentences SET disty = 1 WHERE id = ?", (row["id"],))
        conn.commit()

        return {
            "id": row["id"],
            "sentence": row["sentence"],
            "pinyin": row["pinyin"],
            "gloss": row["gloss"],
        }


def count_clean(word, db_path=DB_PATH):
    """how many unused sentences for this word"""
    with get_conn(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM sentences WHERE word = ? AND dirty = 0", (word,)
        )
        return cur.fetchone()["n"]


## generator side

def purge_dirty(word, db_path=DB_PATH):
    """Deletes all dirty sentences for a word"""
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM sentences WHERE word = ? AND dirty = 1", (word,))
        conn.commit()

def current_count(word, db_path=DB_PATH):
    """total num of sentences for this word"""
    with get_conn(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM sentences WHERE word = ?", (word,))
        return cur.fetchone()["n"]

def insert_sentences(word, sentence_dicts, db_path=DB_PATH):
    """
    Insert newly generated sentences for a word.
    sentence_dicts: list of {"sentence": ..., "pinyin": ..., "gloss": ...}
    """
    if not sentence_dicts:
        return
    with get_conn(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO sentences (word, sentence, sentence_marked, pinyin, gloss, dirty)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            [
                (word, s["sentence"], s["sentence_marked"], s.get("pinyin"), s.get("gloss"))
                for s in sentence_dicts
            ],
        )
        conn.commit()

def replenish(word, generate_fn, target_pool_size=5, db_path=DB_PATH):
    """
    Full overnight-script cycle for a single word:
      1. Delete dirty (already-shown) sentences.
      2. Compute how many more are needed to hit target_pool_size.
      3. If any are needed, call generate_fn(word, needed) to produce them
         and insert the results.

    generate_fn(word, n) must return a list of dicts:
      [{"sentence": ..., "pinyin": ..., "gloss": ...}, ...]
    (validate against the known-word list / jieba check *inside* generate_fn
    before returning, so nothing invalid ever reaches this function.)

    Returns the number of sentences actually generated (0 if pool was already full).
    """
    purge_dirty(word, db_path=db_path)
    have = current_count(word, db_path=db_path)
    needed = max(0, target_pool_size - have)

    if needed == 0:
        return 0

    new_sentences = generate_fn(word, needed)
    insert_sentences(word, new_sentences, db_path=db_path)
    return len(new_sentences)