# Copyright: Arthur Milchior arthur@milchior.fr
#            2017 Glutanimate
#            2019- ijgnd
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

import uuid
from pprint import pprint as pp

import anki.notes
from anki.hooks import addHook
from anki.utils import intTime, guid64
from aqt import mw
from aqt.browser import Browser
from aqt.qt import *
from aqt.utils import askUser, tooltip

from .config import gc
from .choosers import selected_new_deck_name, selected_new_model_name
from .helpers import fields_to_fill_for_nonempty_front_template
from .menu_key_navigation import qtkey_from_config, keyFilter, alternative_keys
from .utils import createRelationTag, getRelationsFromNote


def copyLog(data, newCid):
    id, cid, usn, ease, ivl, lastIvl, factor, time, type = data
    id = timestampID(mw.col.db, "revlog", t=id)
    cid = newCid
    mw.col.db.execute("insert into revlog values (?, ?, ?, ?, ?, ?, ?, ?, ?)", id, cid, usn, ease, ivl, lastIvl, factor, time, type)


def timestampID(db, table, t=None, before=False):
    "Return a non-conflicting timestamp for table."
    # be careful not to create multiple objects without flushing them, or they
    # may share an ID.
    t = t or intTime(1000)
    while db.scalar("select id from %s where id = ?" % table, t):
        if before:
            t -= 1
        else:
            t += 1
    return t


def adjusted_diff(higher, lower, towardslower):
    diff = higher - lower
    # limit diff, if you are on a 10 day vacation and late want to insert a note before
    # the first one created after the holiday this inserted note would be 5 days older.
    # That's confusing. so limit to 10 seconds. 
    diff = min(diff, 10000) 
    #diff = int(diff/2)  # downside: doesn't give many options for insertions: maybe I want to 
                         # add 20 notes around a long note/IR note.
    diff = int(diff/2)
    return diff


def timestampID_Middle(db, table, oldnid, before=False):
    """Return a non-conflicting timestamp for table. Don't use the next free one but so 
    that other notes may be inserted later.
    """
    # be careful not to create multiple objects without flushing them, or they
    # may share an ID.
    ids = db.list("select id from notes")
    ids.sort()
    idx = ids.index(oldnid)
    if idx == 0:
        return oldnid - 1 
    elif before:
        prior = ids[idx-1]
        if prior + 1 == oldnid:  # there's no middle. Auto search next free one.
            if askUser("No unused neighboring nid found. Use next free one?"):
                return timestampID(db, table, oldnid, before)
            else:
                return None
        else:
            diff = adjusted_diff(oldnid, prior, False)
            new = oldnid - diff
            # pp(f"oldnid is: {oldnid}, prior is: {prior} and diff is {diff}, new is {new}")
            return new
    else:
        plusone = ids[idx+1]
        if plusone - 1 == oldnid:  # there's no middle. Auto search next free one.
            return timestampID(db, table, oldnid, before)
        else:
            diff = adjusted_diff(plusone, oldnid, True)
            diff = min(diff, 10000)
            new = oldnid + diff        
            # pp(f"oldnid is: {oldnid}, plusone is: {plusone} and diff is {diff}, new is {new}")
            return new


def get_new_did(parent, sourcenid, cidlist):
    if not cidlist:  # allSelectedCids: if multiple cards of same note are selected in the browser
        note = mw.col.getNote(sourcenid)
        return note.did
    sel_cards_of_sourcenid = 0
    useddecks = set([])
    for cid in cidlist:
        card = mw.col.getCard(cid)
        if card.nid == sourcenid:
            useddecks.add(card.did)
            sel_cards_of_sourcenid += 1
    if sel_cards_of_sourcenid > 1:
        useddecknames = []
        for did in useddecks:
            deck = mw.col.decks.get(did)
            useddecknames.append(deck['name'])
        deckname = selected_new_deck_name(parent, useddecknames)
        source_did = mw.col.decks.byName(deckname)['id']
    else:
        source_did = list(useddecks)[0]
    return source_did


def get_model(parent, sourcenid, keepNotetype):
    if keepNotetype:
        note = mw.col.getNote(sourcenid)
        model = mw.col.models.get(note.mid)
    else:
        newname = selected_new_model_name(parent)
        model = mw.col.models.byName(newname)
    return model


def get_new_nid(sourcenid, keepCreationTime):
    oldid = sourcenid if keepCreationTime else None
    if not oldid:
        newnid = timestampID(mw.col.db, "notes", oldid, before=False)
    else:
        if keepCreationTime == "before":
            before = True
        else:
            before = False
        newnid = timestampID_Middle(mw.col.db, "notes", oldid, before)
    return newnid


def create_new_empty_note(model, did=None, newnid=None, fields=None, tags=None):
    # source card is relevant to determine the new deck: If only one card for the note is 
    # selected use its deck, else ask user
    if did:
        source_deck = mw.col.decks.get(did)
        # Assign model to deck
        mw.col.decks.select(did)
        source_deck['mid'] = model['id']
        mw.col.decks.save(source_deck)
    # Assign deck to model
    mw.col.models.setCurrent(model)
    model['did'] = did
    mw.col.models.save(model)
    
    # Create new note
    new_note = mw.col.newNote()
    if newnid:
        new_note.id = newnid
    if fields:
        new_note.fields = fields
    else:
        # original solution: fill all fields to avoid notes without cards
        #    fields = ["."] * len(new_note.fields)
        # problem: That's a hassle for note types that generate e.g. up to 20 cards ...
        # for details see helpers.py
        new_note.fields = [""] * len(new_note.fields)
        tofill = fields_to_fill_for_nonempty_front_template(new_note.mid)
        if not tofill:  # no note of the note type exists
            new_note.fields = ["."] * len(new_note.fields)
        else:
            for i in tofill:
                new_note.fields[i] = "."

    if tags:
        new_note.tags = tags
    if gc("relate copies"):
        new_note.addTag(createRelationTag())

    # Refresh note and add to database
    new_note.flush()
    mw.col.addNote(new_note)


def new_note(parent, sourcenid, cidlist, keepNotetype, keepCreationTime, tags):
    did = get_new_did(parent, sourcenid, cidlist)
    model = get_model(parent, sourcenid, keepNotetype)
    newnid = get_new_nid(sourcenid, keepCreationTime)
    if newnid:
        create_new_empty_note(model, did, newnid, fields=None, tags=tags)

# Do I need to adjust the cids?
# + looks nicer, who knows why I might need this in the future
# - more error prone!
# - not necessary for filtered decks: custom study in "order created" sorts by "n.id"
def copyCard(card, note, keepCreationTime, keepIvlEtc, log):
    oid = card.id
    t = card.id if keepCreationTime else None
    if t and keepCreationTime == "before":
        before = True
    else:
        before = False
    # card.id = timestampID(note.col.db, "cards", t, before)
    # the line on top was replaced in the original by Arthur for 2.1.25, see 
    # https://github.com/Arthur-Milchior/anki-copy-note/commit/91fa298e527a93f95d97c5671fd6cb5dbf138f14 
    # Setting id to 0 is Card is seen as new; which lead to a different process in backend
    card.id = 0
    new_cid = timestampID(note.col.db, "cards", t, before)

    if not keepIvlEtc:
        card.type = 0
        card.ivl = 0
        card.factor = 0
        card.reps = 0
        card.lapses = 0
        card.left = 0
        card.odue = 0
    card.nid = note.id
    card.flush()
    if t:
        mw.col.db.execute("update Cards set id = ? where id = ?", new_cid, card.id)
        card.id = new_cid
    if log:
        for data in mw.col.db.all("select * from revlog where id = ?", oid):
            copyLog(data, card.id)


def duplicate_note(sourcenid, keepCreationTime, keepIvlEtc, keepLog):
    note = mw.col.getNote(sourcenid)
    cards = note.cards()
    oldid = note.id if keepCreationTime else None
    if not oldid:
        note.id = timestampID(note.col.db, "notes", oldid, before=False)
    else:
        if keepCreationTime == "before":
            before = True
        else:
            before = False
        note.id = timestampID_Middle(note.col.db, "notes", oldid, before)
    note.guid = guid64()
    for card in cards:
        copyCard(card, note, keepCreationTime, keepIvlEtc, keepLog)
    note.flush()


def copyNotes(browser, nidlist, cidlist, keepNotetype, keepCreationTime, keepIvlEtc, keepLog, keepContent):
    pp(f"browser: {browser}, keepNotetype: {keepNotetype}, time:{keepCreationTime}, keepIvlEtc:{keepIvlEtc}, log:{keepLog}, keepContent: {keepContent}", width=130)
    if not nidlist:
        tooltip("no notes selected. Aborting")
        return
    mw.checkpoint("Copy Notes")
    for nid in nidlist:
        if keepContent:
            mw.progress.start()
            note = mw.col.getNote(nid)
            duplicate_note(nid, keepCreationTime, keepIvlEtc, keepLog)
            msg = "Cards copied."
            mw.progress.finish()
        else:
            note = mw.col.getNote(nid)
            new_note(browser, note.id, cidlist, keepNotetype, keepCreationTime, note.tags)
            msg = "New note inserted."
        if gc("relate copies") and not getRelationsFromNote(note):
            note.addTag(createRelationTag())
            note.flush()       
    mw.col.reset()
    mw.reset()
    tooltip(msg)


def cNFB(browser, keepNotetype=True, keepCreationTime=True, keepIvlEtc=True, keepLog=True, keepContent=True):
    allSelectedCids = browser.selectedCards()
    nidlist = browser.selectedNotes()
    browser.editor.saveNow(lambda b=browser, nl=nidlist, asc=allSelectedCids: copyNotes(b, nl, asc, keepNotetype, keepCreationTime, keepIvlEtc, keepLog, keepContent))


basic_stylesheet = """
QMenu::item {
    padding-top: 16px;
    padding-bottom: 16px;
    padding-right: 75px;
    padding-left: 20px;
    font-size: 15px;
}
QMenu::item:selected {
    background-color: #fd4332;
}
"""

requiredKeys = [
    "label",
    # "shortcut",  # not necessary for menu so I add it later only for the shortcuts
    # I can just use .get() and default values?
    # "keepCreationTime",
    # "keepIvlEtc",
    # "keepLog",
    # "keepContent",
]


def menu_cut_helper(browser, entry):
    cNFB(browser=browser, 
                         keepNotetype=entry.get("keep-note-type", True),
                         keepCreationTime=entry.get("keepCreationTime", False), 
                         keepIvlEtc=entry.get("keepIvlEtc", False), 
                         keepLog=entry.get("keepLog", False), 
                         keepContent=entry.get("keepContent", True))


# don't use the code from quick note menu: too complicated
def mymenu(browser):
    outermenu = QMenu(mw)
    outermenu.setStyleSheet(basic_stylesheet)
    quicksets = gc("quicksets")
    directCommands = {}
    if quicksets:
        for entry in quicksets:
            for k in requiredKeys:
                if not k in entry:
                    continue
            n = uuid.uuid4()   
            directCommands[n] = outermenu.addAction(entry["label"])
            directCommands[n].triggered.connect(lambda _, b=browser, e=entry: menu_cut_helper(b,e))
    # """
    c = QMenu("custom ...")
    c.setStyleSheet(basic_stylesheet)
    outermenu.addMenu(c)

    p = QMenu("preserve creation time ...")
    p.setStyleSheet(basic_stylesheet)
    c.addMenu(p)
    n = QMenu("don't ...")
    n.setStyleSheet(basic_stylesheet)
    c.addMenu(n)

    pa = QMenu("after")
    pa.setStyleSheet(basic_stylesheet)
    p.addMenu(pa)
    pb = QMenu("before")
    pb.setStyleSheet(basic_stylesheet)
    p.addMenu(pb)

    pa_props = QMenu("preserve ease, due, interval")
    pa_props.setStyleSheet(basic_stylesheet)
    pa.addMenu(pa_props)
    pa_none = QMenu("don't")
    pa_none.setStyleSheet(basic_stylesheet)
    pa.addMenu(pa_none)

    pb_props = QMenu("preserve ease, due, interval")
    pb_props.setStyleSheet(basic_stylesheet)
    pb.addMenu(pb_props)
    pb_none = QMenu("don't")
    pb_none.setStyleSheet(basic_stylesheet)
    pb.addMenu(pb_none)

    n_props = QMenu("preserve ease, due, interval")
    n_props.setStyleSheet(basic_stylesheet)
    n.addMenu(n_props)
    n_none = QMenu("don't")
    n_none.setStyleSheet(basic_stylesheet)
    n.addMenu(n_none)

    x1 = pa_props.addAction("keep log")
    x1.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="after", keepIvlEtc=True, keepLog=True, keepContent=True))
    x2 = pa_props.addAction("don't")
    x2.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="after", keepIvlEtc=True, keepLog=False, keepContent=True))
    x3 = pa_none.addAction("keep log")
    x3.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="after", keepIvlEtc=False, keepLog=True, keepContent=True))
    x4 = pa_none.addAction("don't")
    x4.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="after", keepIvlEtc=False, keepLog=False, keepContent=True))

    x1 = pb_props.addAction("keep log")
    x1.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="before", keepIvlEtc=True, keepLog=True, keepContent=True))
    x2 = pb_props.addAction("don't")
    x2.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="before", keepIvlEtc=True, keepLog=False, keepContent=True))
    x3 = pb_none.addAction("keep log")
    x3.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="before", keepIvlEtc=False, keepLog=True, keepContent=True))
    x4 = pb_none.addAction("don't")
    x4.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime="before", keepIvlEtc=False, keepLog=False, keepContent=True))

    x5 = n_props.addAction("keep log")
    x5.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime=False, keepIvlEtc=True, keepLog=True, keepContent=True))
    x6 = n_props.addAction("don't")
    x6.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime=False, keepIvlEtc=True, keepLog=False, keepContent=True))
    x7 = n_none.addAction("keep log")
    x7.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime=False, keepIvlEtc=False, keepLog=True, keepContent=True))
    x8 = n_none.addAction("don't")
    x8.triggered.connect(lambda _, n=browser: cNFB(browser=n, keepCreationTime=False, keepIvlEtc=False, keepLog=False, keepContent=True))
    #"""

    if gc("menu_use_alternative_keys_for_navigation"):
        for m in [outermenu, c, p, n, pa, pb, pa_props, pa_none, pb_props, pb_none, n_props, n_none]:
        # for m in [outermenu]:
            menufilter = keyFilter(m)
            m.installEventFilter(menufilter)
            m.alternative_keys = alternative_keys
    outermenu.exec(QCursor.pos())


def setupMenu(browser):
    global noteCopyAction
    self = browser
    noteCopyAction = QAction("Note Copy", browser)
    key = gc("Shortcut__menu")
    if key:
        noteCopyAction.setShortcut(QKeySequence(key))
    noteCopyAction.triggered.connect(lambda _, b=browser: mymenu(b))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(noteCopyAction)

    # add global shortcuts:
    quicksets = gc("quicksets")
    directCommands = {}
    if quicksets:
        extended = requiredKeys + ["shortcut"]
        for entry in quicksets:
            for k in extended:
                if not k in entry :
                    continue
            n = uuid.uuid4()
            directCommands[n] = QShortcut(QKeySequence(entry["shortcut"]), self) 
            qconnect(directCommands[n].activated, lambda b=browser, e=entry: menu_cut_helper(b,e))
addHook("browser.setupMenus", setupMenu)


def add_to_table_context_menu(browser, menu):
    menu.addAction(noteCopyAction)
addHook("browser.onContextMenu", add_to_table_context_menu)






def add_to_context(view, menu):
    if gc("editor context menu in browser show new before/after"):
        browser = view.editor.parentWindow
        if not isinstance(browser, Browser):
            return
        a = menu.addAction("Copy note")
        a.triggered.connect(lambda _, b=browser: mymenu(b))
addHook("EditorWebView.contextMenuEvent", add_to_context)
