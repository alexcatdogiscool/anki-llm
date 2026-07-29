import re

import re

MARKER_RE = re.compile(r"\{\{(.+?)\}\}")

PLACEHOLDER_RE = re.compile(r"\bsb\.?|\bsth\.?", re.IGNORECASE)

def word_is_template(word):
    return bool(PLACEHOLDER_RE.search(word))

def build_marker_pattern(word):
    """
    Turn a template like '问 sb. 好' into a regex that matches any
    substitution, e.g. r'问.+?好'
    """
    parts = PLACEHOLDER_RE.split(word)
    parts = [re.escape(p.strip()) for p in parts if p.strip()]
    return re.compile(".+?".join(parts))

def postprocess(word, parsed_sentences, known_words=None):
    """
    Filter a list of {"sentence", "pinyin", "gloss"} dicts down to only the
    ones with a valid {{target_word}} marker. Strips the markers before
    returning.

    known_words is accepted but unused for now — kept so the call site
    doesn't need to change later when vocabulary checking gets added back in.
    """
    valid = []

    for d in parsed_sentences:
        if not isinstance(d, dict) or "sentence" not in d:
            print(f"  [{word}] REJECTED (malformed entry): {d!r}")
            continue

        raw_sentence = d["sentence"]

        if raw_sentence.count("{{") != 1:
            print(f"  [{word}] REJECTED (marker count != 1): {raw_sentence!r}")
            continue

        match = MARKER_RE.search(raw_sentence)
        if not match:
            print(f"  [{word}] REJECTED (no marker found): {raw_sentence!r}")
            continue

        if word_is_template(word):
            pattern = build_marker_pattern(word)
            if not pattern.fullmatch(match.group(1)):
                print(f"  [{word}] REJECTED (marker '{match.group(1)}' doesn't match template): {raw_sentence!r}")
                continue
        else:
            if match.group(1) != word:
                print(f"  [{word}] REJECTED (marker wraps '{match.group(1)}', expected '{word}'): {raw_sentence!r}")
                continue

        clean_sentence = MARKER_RE.sub(lambda m: m.group(1), raw_sentence)

        valid.append({
            "sentence": clean_sentence,
            "sentence_marked": raw_sentence,
            "pinyin": d.get("pinyin"),
            "gloss": d.get("gloss"),
        })

    return valid