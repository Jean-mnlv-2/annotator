#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QPushButton,
    QHBoxLayout, QDialogButtonBox, QFileDialog, QLabel, QPlainTextEdit
)


class ExportDialog(QDialog):
    """Unifie l'export (COCO/YOLO/VOC) avec prévisualisation et erreurs lisibles."""

    def __init__(self, parent=None, current_image_path: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Exporter les annotations")
        self.resize(560, 440)

        self.current_image_path = current_image_path

        root = QVBoxLayout(self)

        form = QFormLayout()
        root.addLayout(form)

        self.format_combo = QComboBox(self)
        self.format_combo.addItems(["PascalVOC", "YOLO", "COCO"])
        form.addRow("Format", self.format_combo)

        path_row = QHBoxLayout()
        self.output_edit = QLineEdit(self)
        browse_btn = QPushButton("Parcourir…", self)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.output_edit)
        path_row.addWidget(browse_btn)
        form.addRow("Fichier/Dossier", path_row)

        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Aperçu du fichier d'export ou messages d'erreur…")
        root.addWidget(QLabel("Aperçu / Messages"))
        root.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.format_combo.currentIndexChanged.connect(self._update_suggested_path)
        self._update_suggested_path()

    def _browse(self):
        fmt = self.format_combo.currentText().lower()
        if fmt == "coco":
            path, _ = QFileDialog.getSaveFileName(self, "Exporter COCO", "", "JSON (*.json)")
        elif fmt == "yolo":
            # YOLO: dossier ou .txt (par image); on propose un dossier
            path = QFileDialog.getExistingDirectory(self, "Exporter YOLO", "")
        else:
            # Pascal VOC: XML (par image); fichier par image
            path, _ = QFileDialog.getSaveFileName(self, "Exporter PascalVOC", "", "XML (*.xml)")
        if path:
            self.output_edit.setText(path)

    def _update_suggested_path(self):
        if not self.current_image_path:
            return
        import os
        base, _ = os.path.splitext(self.current_image_path)
        fmt = self.format_combo.currentText().lower()
        if fmt == "coco":
            self.output_edit.setText(base + ".json")
        elif fmt == "yolo":
            self.output_edit.setText(os.path.dirname(self.current_image_path))
        else:
            self.output_edit.setText(base + ".xml")

    def get_selection(self):
        return self.format_combo.currentText(), self.output_edit.text().strip()

    def set_preview_text(self, text: str):
        try:
            self.preview.setPlainText(text or "")
        except Exception:
            pass


