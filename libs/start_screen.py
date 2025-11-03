#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QLineEdit, QFormLayout, QDialogButtonBox
)


class StartScreen(QDialog):
    """Écran d’accueil: Nouveau projet / Ouvrir projet / Récents."""

    def __init__(self, parent=None, recent_projects: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("AKOUMA Annotator — Démarrer")
        self.resize(640, 420)
        root = QVBoxLayout(self)

        title = QLabel("Bienvenue dans AKOUMA Annotator")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # Récents
        self.recent_list = QListWidget(self)
        for p in recent_projects or []:
            QListWidgetItem(p, self.recent_list)
        root.addWidget(QLabel("Projets récents"))
        root.addWidget(self.recent_list)

        # Actions
        row = QHBoxLayout()
        root.addLayout(row)
        self.btn_open = QPushButton("Ouvrir un projet…", self)
        self.btn_new = QPushButton("Nouveau projet…", self)
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_new)
        row.addStretch(1)

        # Nouveau projet form (lazy)
        self._new_form = QDialog(self)
        self._new_form.setWindowTitle("Nouveau projet…")
        form = QFormLayout(self._new_form)
        self.edt_name = QLineEdit(self._new_form)
        self.edt_path = QLineEdit(self._new_form)
        self.edt_images = QLineEdit(self._new_form)
        pick_path = QPushButton("…", self._new_form)
        pick_images = QPushButton("…", self._new_form)
        def _pick_dir(target: QLineEdit):
            d = QFileDialog.getExistingDirectory(self._new_form, "Choisir un dossier")
            if d:
                target.setText(d)
        pick_path.clicked.connect(lambda: _pick_dir(self.edt_path))
        pick_images.clicked.connect(lambda: _pick_dir(self.edt_images))
        path_row = QHBoxLayout(); path_row.addWidget(self.edt_path); path_row.addWidget(pick_path)
        img_row = QHBoxLayout(); img_row.addWidget(self.edt_images); img_row.addWidget(pick_images)
        form.addRow("Nom", self.edt_name)
        form.addRow("Dossier projet", path_row)
        form.addRow("Dossier images", img_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self._new_form)
        form.addRow(buttons)
        buttons.accepted.connect(self._new_form.accept)
        buttons.rejected.connect(self._new_form.reject)

        # Signaux
        self.btn_open.clicked.connect(self._on_open)
        self.btn_new.clicked.connect(self._on_new)
        self.recent_list.itemDoubleClicked.connect(lambda _: self.accept())

        self.selected_project: Optional[str] = None
        self.new_project_params = None  # (name, path, image_dir)

    def _on_open(self):
        path = QFileDialog.getExistingDirectory(self, "Ouvrir un projet")
        if path:
            self.selected_project = path
            self.accept()

    def _on_new(self):
        if self._new_form.exec_() == QDialog.Accepted:
            name = self.edt_name.text().strip()
            path = self.edt_path.text().strip()
            img = self.edt_images.text().strip()
            if name and path and img:
                self.new_project_params = (name, path, img)
                self.accept()

    def get_selected_recent(self) -> Optional[str]:
        if self.selected_project:
            return self.selected_project
        item = self.recent_list.currentItem()
        return item.text() if item else None


