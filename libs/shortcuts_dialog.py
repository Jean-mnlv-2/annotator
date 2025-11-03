#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialogButtonBox, QWidget, QHBoxLayout, QPushButton, QLineEdit, QLabel
)

from libs.shortcut_manager import get_shortcut_manager, ShortcutAction


class ShortcutsDialog(QDialog):
    """Éditeur simple des raccourcis clavier."""

    def __init__(self, parent=None, shortcut_manager: Optional[object] = None):
        super().__init__(parent)
        self.setWindowTitle("Raccourcis clavier")
        self.resize(720, 520)
        self.setModal(True)

        self.shortcut_manager = shortcut_manager or get_shortcut_manager()

        root = QVBoxLayout(self)

        # Filtre
        filter_row = QHBoxLayout()
        root.addLayout(filter_row)
        filter_row.addWidget(QLabel("Filtrer:"))
        self.filter_edit = QLineEdit(self)
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit)

        # Table des raccourcis
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Action", "Description", "Raccourci"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        root.addWidget(self.table)

        # Boutons
        buttons = QDialogButtonBox(QDialogButtonBox.Close | QDialogButtonBox.Save, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        root.addWidget(buttons)

        self._populate()

    def _populate(self):
        actions = sorted(self.shortcut_manager.get_all_actions(), key=lambda a: a.name.lower())
        self._all_actions = actions
        self._render_rows(actions)

    def _render_rows(self, actions):
        self.table.setRowCount(len(actions))
        for row, action in enumerate(actions):
            self.table.setItem(row, 0, QTableWidgetItem(action.name))
            self.table.setItem(row, 1, QTableWidgetItem(action.description))
            # Raccourci éditable
            editor = QLineEdit(self)
            editor.setText(action.current_key)
            editor.setProperty("action_id", action.id)
            self.table.setCellWidget(row, 2, editor)

    def _apply_filter(self, text: str):
        text = (text or "").lower().strip()
        if not text:
            self._render_rows(self._all_actions)
            return
        filtered = [a for a in self._all_actions if text in a.name.lower() or text in a.description.lower()]
        self._render_rows(filtered)

    def _save(self):
        # Lire les valeurs de la colonne 2
        for row in range(self.table.rowCount()):
            editor = self.table.cellWidget(row, 2)
            if not isinstance(editor, QLineEdit):
                continue
            new_key = editor.text().strip()
            action_id = editor.property("action_id")
            if not action_id:
                continue
            if new_key:
                self.shortcut_manager.change_shortcut(action_id, new_key)
        # Persistance via ShortcutManager
        try:
            self.shortcut_manager.save_settings()
        except Exception:
            pass
        self.accept()


