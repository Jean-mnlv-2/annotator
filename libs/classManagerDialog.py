try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *


class ClassManagerDialog(QDialog):

    def __init__(self, classes=None, parent=None):
        super(ClassManagerDialog, self).__init__(parent)
        self.setWindowTitle('Manage Classes')
        self._classes = list(classes or [])

        self.list_widget = QListWidget(self)
        for c in self._classes:
            self.list_widget.addItem(c)

        self.add_button = QPushButton('Add')
        self.remove_button = QPushButton('Remove')
        self.rename_button = QPushButton('Rename')

        self.add_button.clicked.connect(self._on_add)
        self.remove_button.clicked.connect(self._on_remove)
        self.rename_button.clicked.connect(self._on_rename)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        left = QVBoxLayout()
        left.addWidget(self.list_widget)

        right = QVBoxLayout()
        right.addWidget(self.add_button)
        right.addWidget(self.remove_button)
        right.addWidget(self.rename_button)
        right.addStretch(1)

        hl = QHBoxLayout()
        hl.addLayout(left)
        hl.addLayout(right)

        layout = QVBoxLayout()
        layout.addLayout(hl)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.resize(420, 360)

    def _on_add(self):
        text, ok = QInputDialog.getText(self, 'Add Class', 'Class name:')
        if ok:
            text = text.strip()
            if text and text not in self._classes:
                self._classes.append(text)
                self.list_widget.addItem(text)

    def _on_remove(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        self._classes = [c for c in self._classes if c != name]
        self.list_widget.takeItem(self.list_widget.row(item))

    def _on_rename(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        old = item.text()
        text, ok = QInputDialog.getText(self, 'Rename Class', 'New name:', text=old)
        if ok:
            text = text.strip()
            if text and text not in self._classes:
                idx = self._classes.index(old)
                self._classes[idx] = text
                item.setText(text)

    def get_classes(self):
        return list(self._classes)


