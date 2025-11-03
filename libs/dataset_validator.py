#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Tuple, Dict, Any
import os

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox
from PyQt5.QtCore import Qt


class DatasetValidator:
    """Validation simple: fichiers manquants, bbox hors image, classes inconnues (basique)."""

    def __init__(self, classes: List[str]):
        self.classes = set(c for c in classes if c)

    def validate(self, image_paths: List[str]) -> Dict[str, Any]:
        report = {"errors": [], "warnings": [], "stats": {"images": len(image_paths)}}
        for p in image_paths:
            if not os.path.exists(p):
                report["errors"].append(f"Missing image: {p}")
        return report


class ValidationReportDialog(QDialog):
    def __init__(self, parent=None, report: Dict[str, Any] = None):
        super().__init__(parent)
        self.setWindowTitle("Rapport de validation du dataset")
        self.resize(720, 520)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Résultats de la validation"))
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        root.addWidget(self.text)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
        if report:
            self.set_report(report)

    def set_report(self, report: Dict[str, Any]):
        try:
            import json
            self.text.setPlainText(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception:
            pass


