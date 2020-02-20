# this file contains the original debug.py from 
#
# this file also includes from copyNote.py the _uniquifyNote part
#    see https://github.com/Arthur-Milchior/anki-copy-note/blob/ea591e790ae0400f5183783df3e8f6c93e2362ae/copyNote.py#L113
#
# I didn't inlude "_importNotes" from copyNote.py since this method is called nowehere, see
#   https://github.com/Arthur-Milchior/anki-copy-note/blob/ea591e790ae0400f5183783df3e8f6c93e2362ae/copyNote.py#L152


from anki.hooks import addHook
from anki.importing.anki2 import Anki2Importer
from anki.utils import guid64
from aqt import mw
from aqt.utils import askUser

from .config import gc


def check():
    checkedGui = gc("checkedGui", [])
    if mw.pm.name in checkedGui:
        return
    lastGuid = None
    accepted = False
    for guid, nid in mw.col.db.all("select guid, id from notes order by guid, id"):
        if lastGuid == guid:
            if accepted is False:
                accepted = askUser("A previous version of copy note created a bug. Correcting it will require to do a full sync of your collection. Do you want to correct it now ?")
            if accepted is False:
                return
            mw.col.modSchema(True)
            mw.col.db.execute("update notes set guid = ? where id = ? ", guid64(), nid)
        lastGuid = guid
    checkedGui.append(mw.pm.name)

addHook("profileLoaded", check)




###################
# from copyNote.py

firstBug = False
NID = 0
GUID = 1
MID = 2
MOD = 3
# determine if note is a duplicate, and adjust mid and/or guid as required
# returns true if note should be added
def _uniquifyNote(self, note):
    global firstBug
    srcMid = note[MID]
    dstMid = self._mid(srcMid)

    if srcMid != dstMid:
        # differing schemas and note doesn't exist?
        note[MID] = dstMid
        
    if note[GUID] in self._notes:
        destId, destMod, destMid = self._notes[note[GUID]]
        if note[NID] == destId: #really a duplicate
            if srcMid != dstMid: # schema changed and don't import
                self._ignoredGuids[note[GUID]] = True
            return False
        else: #Probably a copy made by buggy version. Change guid to a new one.
            while note[GUID] in self._notes:
                note[GUID] = guid64()
            if not firstBug:
                firstBug = True
                showWarning("""Hi. Sorry to disturb you. 
The deck you are importing seems to have a bug, created by a version of the add-on 1566928056 before the 26th of september 2019. Can you please tell the author of the imported deck that you were warned of this bug, and that it should update the shared deck to remove the bug ? Please send them the link https://github.com/Arthur-Milchior/anki-copy-note so they can have more informations. And let me know on this link whether there is any trouble. 
Arthur@Milchior.fr""")
                
            return True
    else:
        return True

if gc("correct import", True):
    Anki2Importer._uniquifyNote = _uniquifyNote
