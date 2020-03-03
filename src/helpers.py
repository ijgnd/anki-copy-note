import collections
import re

from aqt import mw

# mod of clayout.py/CardLayout._fieldsOnTemplate 
def myFieldsOnTemplate(fmt):
    matches = re.findall("{{[^#/}]+?}}", fmt)
    charsAllowed = 30
    result = collections.OrderedDict()
    for m in matches:
        # strip off mustache
        m = re.sub(r"[{}]", "", m)
        # strip off modifiers
        m = m.split(":")[-1]
        # don't show 'FrontSide'
        if m == "FrontSide":
            continue

        if m not in result:
            result[m] = True
            charsAllowed -= len(m)
            if charsAllowed <= 0:
                break
    return result.keys()


# I could fill every field with "." to make sure at least one card is generated
# with e.g.       note.fields = ["."] * len(note._model["flds"])
# this is save (and used by the note organizer add-on). But this means that I might
# have to manually delete a lot. This takes a least some seconds
# So it's probably quicker to wait for about five seconds so that Anki finds out
# the minimal amount of fields to fill
# start to empty existing fields:
#   note.fields = [""] * len(note._model["flds"])
# I can't just fill all the fields named in the first template because of conditional
# replacement.
# I can't randomly try out all combinations ...
# I have never read the code for card generation so it should take some time
# to extract the relevant code
# Instead use ugly workaround:
#    - get existing notes that generate a card 1
#    - narrow down to notes with the fewest cards generated
#    - narrow down to a note with the fewest fields filled
#    - only fill these fields
def fields_to_fill_for_nonempty_front_template(mid):
    wco = mw.col.findCards("mid:%s card:1" %mid)
    totalcards = {}
    for cid in wco:
        card = mw.col.getCard(cid)
        totalcards.setdefault(card.nid, 0)
        totalcards[card.nid] += 1
    nid_filled_map = {}
    for nid, number_of_cards in totalcards.items():
        if number_of_cards == 1:
            othernote = mw.col.getNote(nid)
            nid_filled_map[nid] = 0
            for f in othernote.fields:
                if f:
                    nid_filled_map[nid] += 1
    lowestnid = min(nid_filled_map, key=nid_filled_map.get)
    othernote = mw.col.getNote(lowestnid)
    tofill = []
    for idx, cont in enumerate(othernote.fields):
        if cont:
            tofill.append(idx)
    return tofill
