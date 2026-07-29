
from aqt import gui_hooks
from anki.cards import Card
from anki import hooks
from anki.template import TemplateRenderContext, TemplateRenderOutput
import sqlite3

DATABASE_PATH = "/home/alex/Desktop/programming/anki-plugin/llm/sentences.db"

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
    entry = options[1]

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
    
    



hooks.card_did_render.append(render_new)

