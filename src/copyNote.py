# Copyright: Arthur Milchior arthur@milchior.fr
#            ijgnd           
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

import uuid
from pprint import pprint as pp

import anki.notes
from anki.hooks import addHook
from anki.lang import _
from anki.utils import intTime, guid64
from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

from .config import gc
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


def timestampID_Middle(db, table, oldnid, before=False):
    """Return a non-conflicting timestamp for table. Don't use the next free one but one
    that is in the middle to the next one so that other cards may be inserted later."""
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
            return timestampID(db, table, oldnid, before)
        else:
            diff = int((oldnid - prior)/2)
            return oldnid - diff
    else:
        prior = ids[idx+1]
        if prior - 1 == oldnid:  # there's no middle. Auto search next free one.
            return timestampID(db, table, oldnid, before)
        else:
            diff = int((oldnid - prior)/2)
            return oldnid + diff        


def copyCard(card, note, keepCreationTime, keepIvlEtc, log):
    oid = card.id
    t = card.id if keepCreationTime else None
    if t and keepCreationTime == "before":
        before = True
    else:
        before = False
    card.id = timestampID(note.col.db, "cards", t, before)
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
    if log:
        for data in mw.col.db.all("select * from revlog where id = ?", oid):
            copyLog(data, card.id)


def copyNote(nid, keepCreationTime, keepIvlEtc, keepLog, keepContent):
    note = mw.col.getNote(nid)
    cards = note.cards()
    if gc("relate copies", False):
        if not getRelationsFromNote(note):
            note.addTag(createRelationTag())
            note.flush()
    t = note.id if keepCreationTime else None
    if t and keepCreationTime == "before":
        before = True
    else:
        before = False
    note.id = timestampID(note.col.db, "notes", t, before)
    #print(f"old note id: {note.id}")
    #note.id = timestampID_Middle(note.col.db, "notes", t, before)
    #print(f"new note id: {note.id}")
    note.guid = guid64()
    if not keepContent:
        note.fields = ["."] * len(note._model["flds"])
        # it doesn't make to copy a review history and intervals for new and empty cards
        keepIvlEtc = False
        keepLog = False
    for card in cards:
        copyCard(card, note, keepCreationTime, keepIvlEtc, keepLog)
    note.flush()


def copyNotes(nidlist, keepCreationTime=True, keepIvlEtc=True, keepLog=True, keepContent=True):
    pp(f"nids:{nidlist}, time:{keepCreationTime}, keepIvlEtc:{keepIvlEtc}, log:{keepLog}, keepContent: {keepContent}")
    if not nidlist:
        tooltip("no notes selected. Aborting")
        return
    mw.checkpoint("Copy Notes")
    mw.progress.start()
    for nid in nidlist:
        copyNote(nid, keepCreationTime, keepIvlEtc, keepLog, keepContent)
    # Reset collection and main window
    mw.progress.finish()
    mw.col.reset()
    mw.reset()
    tooltip(_("Cards copied."))


def copyNotesFromBrowser(browser, keepCreationTime=True, keepIvlEtc=True, keepLog=True, keepContent=True):
    browser.editor.saveNow(lambda b=browser.selectedNotes(): copyNotes(b, keepCreationTime, keepIvlEtc, keepLog, keepContent))


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
    "keepCreationTime",
    "keepIvlEtc",
    "keepLog",
    "keepContent",
]

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
            directCommands[n].triggered.connect(lambda _,
                                                       b=browser,
                                                       kct=entry["keepCreationTime"],
                                                       ivl=entry["keepIvlEtc"],
                                                       log=entry["keepLog"],
                                                       cont=entry["keepContent"]: copyNotesFromBrowser(
                                                                        browser=b, 
                                                                        keepCreationTime=kct, 
                                                                        keepIvlEtc=ivl, 
                                                                        keepLog=log, 
                                                                        keepContent=cont))
    # d1 = outermenu.addAction("keep everything (after)")
    # d1.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="after", keepIvlEtc=True, keepLog=True, keepContent=True))
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
    x1.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="after", keepIvlEtc=True, keepLog=True, keepContent=True))
    x2 = pa_props.addAction("don't")
    x2.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="after", keepIvlEtc=True, keepLog=False, keepContent=True))
    x3 = pa_none.addAction("keep log")
    x3.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="after", keepIvlEtc=False, keepLog=True, keepContent=True))
    x4 = pa_none.addAction("don't")
    x4.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="after", keepIvlEtc=False, keepLog=False, keepContent=True))

    x1 = pb_props.addAction("keep log")
    x1.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="before", keepIvlEtc=True, keepLog=True, keepContent=True))
    x2 = pb_props.addAction("don't")
    x2.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="before", keepIvlEtc=True, keepLog=False, keepContent=True))
    x3 = pb_none.addAction("keep log")
    x3.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="before", keepIvlEtc=False, keepLog=True, keepContent=True))
    x4 = pb_none.addAction("don't")
    x4.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime="before", keepIvlEtc=False, keepLog=False, keepContent=True))

    x5 = n_props.addAction("keep log")
    x5.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime=False, keepIvlEtc=True, keepLog=True, keepContent=True))
    x6 = n_props.addAction("don't")
    x6.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime=False, keepIvlEtc=True, keepLog=False, keepContent=True))
    x7 = n_none.addAction("keep log")
    x7.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime=False, keepIvlEtc=False, keepLog=True, keepContent=True))
    x8 = n_none.addAction("don't")
    x8.triggered.connect(lambda _, n=browser: copyNotesFromBrowser(browser=n, keepCreationTime=False, keepIvlEtc=False, keepLog=False, keepContent=True))

    if gc("menu_use_alternative_keys_for_navigation", False):
        for m in [outermenu, c, p, n, pa, pb, pa_props, pa_none, pb_props, pb_none, n_props, n_none]:
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
            qconnect(directCommands[n].activated, lambda
                                                       b=browser,
                                                       kct=entry["keepCreationTime"],
                                                       ivl=entry["keepIvlEtc"],
                                                       log=entry["keepLog"],
                                                       cont=entry["keepContent"]: copyNotesFromBrowser(
                                                                        browser=b, 
                                                                        keepCreationTime=kct, 
                                                                        keepIvlEtc=ivl, 
                                                                        keepLog=log, 
                                                                        keepContent=cont))
addHook("browser.setupMenus", setupMenu)


def add_to_table_context_menu(browser, menu):
    menu.addAction(noteCopyAction)
addHook("browser.onContextMenu", add_to_table_context_menu)
