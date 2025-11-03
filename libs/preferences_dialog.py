#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox,
    QCheckBox, QSpinBox, QDialogButtonBox, QLabel, QPushButton, QHBoxLayout
)

from libs.theme_manager import get_theme_manager, ThemeMode


class PreferencesDialog(QDialog):
    """
    Boîte de dialogue des préférences: thème, autosave, raccourcis.
    """

    def __init__(self, parent=None, config_manager: Optional[object] = None, shortcut_manager: Optional[object] = None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")
        self.setModal(True)
        self.resize(520, 420)

        self.config_manager = config_manager
        self.shortcut_manager = shortcut_manager
        self.theme_manager = get_theme_manager()

        root = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs)

        # Onglet Apparence
        self.appearance_tab = QWidget(self)
        self._build_appearance_tab(self.appearance_tab)
        self.tabs.addTab(self.appearance_tab, "Apparence")

        # Onglet Sauvegarde
        self.save_tab = QWidget(self)
        self._build_save_tab(self.save_tab)
        self.tabs.addTab(self.save_tab, "Sauvegarde")

        # Onglet Raccourcis (lien vers éditeur dédié)
        self.shortcuts_tab = QWidget(self)
        self._build_shortcuts_tab(self.shortcuts_tab)
        self.tabs.addTab(self.shortcuts_tab, "Raccourcis")

        # Boutons OK/Annuler
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_values()

    def _build_appearance_tab(self, tab: QWidget):
        layout = QFormLayout(tab)
        # Mode de thème
        self.theme_mode = QComboBox(tab)
        self.theme_mode.addItems(["Clair", "Sombre", "Auto"])
        layout.addRow("Mode du thème", self.theme_mode)

        # Thème (Modern/Classic)
        self.theme_name = QComboBox(tab)
        for name in self.theme_manager.get_available_themes():
            self.theme_name.addItem(name)
        layout.addRow("Thème", self.theme_name)

        # Animations UI
        self.animations_enabled = QCheckBox("Activer les animations d'interface", tab)
        layout.addRow("Animations", self.animations_enabled)

    def _build_save_tab(self, tab: QWidget):
        layout = QFormLayout(tab)
        self.autosave_enabled = QCheckBox("Activer la sauvegarde automatique", tab)
        layout.addRow("Autosave", self.autosave_enabled)

        self.autosave_interval = QSpinBox(tab)
        self.autosave_interval.setRange(10, 3600)
        self.autosave_interval.setSuffix(" s")
        layout.addRow("Intervalle autosave", self.autosave_interval)

        self.backup_enabled = QCheckBox("Créer une sauvegarde (backup)", tab)
        layout.addRow("Backup", self.backup_enabled)

    def _build_shortcuts_tab(self, tab: QWidget):
        layout = QVBoxLayout(tab)
        info = QLabel("Gérez les raccourcis clavier dans l'éditeur dédié.")
        layout.addWidget(info)
        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)
        self.open_shortcuts_btn = QPushButton("Ouvrir l'éditeur de raccourcis", tab)
        self.open_shortcuts_btn.clicked.connect(self._open_shortcuts_editor)
        btn_row.addWidget(self.open_shortcuts_btn)
        btn_row.addStretch(1)

    def _load_values(self):
        # Charger depuis ThemeManager
        tm = self.theme_manager
        # Mode
        if tm.current_mode == ThemeMode.DARK:
            self.theme_mode.setCurrentIndex(1)
        elif tm.current_mode == ThemeMode.AUTO:
            self.theme_mode.setCurrentIndex(2)
        else:
            self.theme_mode.setCurrentIndex(0)
        # Nom du thème
        current_theme_name = tm.current_theme.name if tm.current_theme else "Modern"
        idx = self.theme_name.findText(current_theme_name)
        if idx >= 0:
            self.theme_name.setCurrentIndex(idx)
        self.animations_enabled.setChecked(tm.animations_enabled)

        # Config autosave
        interval = 300
        autosave = True
        backup = True
        if self.config_manager:
            try:
                autosave = bool(self.config_manager.get_value('application.auto_save', True))
                interval = int(self.config_manager.get_value('application.auto_save_interval', 300))
                backup = bool(self.config_manager.get_value('application.backup_enabled', True))
            except Exception:
                pass
        self.autosave_enabled.setChecked(autosave)
        self.autosave_interval.setValue(interval)
        self.backup_enabled.setChecked(backup)

    def accept(self):
        # Appliquer thème
        name = self.theme_name.currentText()
        mode_idx = self.theme_mode.currentIndex()
        if mode_idx == 2:
            self.theme_manager.set_mode(ThemeMode.AUTO)
        elif mode_idx == 1:
            self.theme_manager.set_mode(ThemeMode.DARK)
        else:
            self.theme_manager.set_mode(ThemeMode.LIGHT)
        self.theme_manager.set_theme(name)
        self.theme_manager.set_animations_enabled(self.animations_enabled.isChecked())

        # Appliquer autosave/backups
        if self.config_manager:
            try:
                self.config_manager.set_value('application.auto_save', self.autosave_enabled.isChecked())
                self.config_manager.set_value('application.auto_save_interval', int(self.autosave_interval.value()))
                self.config_manager.set_value('application.backup_enabled', self.backup_enabled.isChecked())
                self.config_manager.save_config()
            except Exception:
                pass

        super().accept()

    def _open_shortcuts_editor(self):
        try:
            from libs.shortcuts_dialog import ShortcutsDialog
        except Exception:
            # L'éditeur peut ne pas exister encore
            return
        dlg = ShortcutsDialog(self, shortcut_manager=self.shortcut_manager)
        dlg.exec_()


