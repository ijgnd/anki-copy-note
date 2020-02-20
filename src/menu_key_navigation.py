from aqt.qt import *

from .config import gc


some_valid_qt_keys = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D",
    "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z", "Space", "Tab", "CapsLock", "F1", "F2", "F3", "F4",
    "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"
]


def qtkey_from_config(value):
    key = gc(value)
    if not key:
        return None
    if not key.title() in some_valid_qt_keys:
        # tooltip("Illegal value for key")
        return None
    return eval('Qt.Key_' + str(key).title())


class keyFilter(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == qtkey_from_config("menu_keyalt_for_return"):
                self.parent.alternative_keys(self.parent, Qt.Key_Return)
                return True
            elif event.key() == qtkey_from_config("menu_keyalt_for_arrow_left"):
                self.parent.alternative_keys(self.parent, Qt.Key_Left)
                return True
            elif event.key() == qtkey_from_config("menu_keyalt_for_arrow_down"):
                self.parent.alternative_keys(self.parent, Qt.Key_Down)
                return True
            elif event.key() == qtkey_from_config("menu_keyalt_for_arrow_up"):
                self.parent.alternative_keys(self.parent, Qt.Key_Up)
                return True
            elif event.key() == qtkey_from_config("menu_keyalt_for_arrow_right"):
                self.parent.alternative_keys(self.parent, Qt.Key_Right)
                return True
        return False


def alternative_keys(self, key):
    # https://stackoverflow.com/questions/56014149/mimic-a-returnpressed-signal-on-qlineedit
    # from PyQt5 import QtCore, QtGui
    # keyEvent = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier)
    # QtCore.QCoreApplication.postEvent(self, keyEvent)
    keyEvent = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)
    QCoreApplication.postEvent(self, keyEvent) 
