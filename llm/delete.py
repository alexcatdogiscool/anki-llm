import sqlite3

ANKI_PATH = "/home/alex/.var/app/net.ankiweb.Anki/data/Anki2/User 1/collection.anki2"
DECK_ID = 1783246160167

conn = sqlite3.connect(f"file:{ANKI_PATH}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Confirm the deck exists and matches this ID
cur.execute("SELECT id, name FROM decks")
all_decks = cur.fetchall()
found = False
for row in all_decks:
    if row["id"] == DECK_ID:
        print(f"Deck found: {row['name']}")
        found = True
if not found:
    print(f"DECK_ID {DECK_ID} NOT FOUND. Available decks:")
    for row in all_decks:
        print(f"  {row['id']}: {row['name']}")

# 2. Raw count + state breakdown for this deck, no filtering
cur.execute("SELECT type, COUNT(*) FROM cards WHERE did = ? GROUP BY type", (DECK_ID,))
print("\nCard state breakdown (0=new,1=learning,2=review,3=relearning):")
for row in cur.fetchall():
    print(f"  type={row[0]}: {row[1]} cards")

# 3. Spot-check a few cards' actual interval/reps/lapses
cur.execute("SELECT id, ivl, reps, lapses, type FROM cards WHERE did = ? LIMIT 10", (DECK_ID,))
print("\nSample cards:")
for row in cur.fetchall():
    print(dict(row))

conn.close()