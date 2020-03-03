from aqt import mw
from aqt.qt import *

from aqt.studydeck import StudyDeck


def selected_new_model_name(parent):
    current = mw.col.models.current()["name"]
    def nameFunc():
        return sorted(mw.col.models.allNames())
    prevent_add_button = QPushButton("")  # type: ignore
    ret = StudyDeck(
        mw,
        names=nameFunc,
        accept="Choose",
        title="Choose Note Type",
        help="_notes",
        current=current,
        parent=parent,
        buttons=[prevent_add_button],
        cancel=False,
        geomKey="mySelectModel",
    )
    return ret.name


def selected_new_deck_name(parent, relevantdecks):
    def nameFunc():
        return sorted(relevantdecks)
    prevent_add_button = QPushButton("")  # type: ignore
    ret = StudyDeck(
        mw,
        names=nameFunc,
        accept="Choose",
        title="Choose Deck",
        help=None,
        current=None,
        parent=parent,
        buttons=[prevent_add_button],
        cancel=False,
        geomKey="mySelectModel",
    )
    return ret.name
