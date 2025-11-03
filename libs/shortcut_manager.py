#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

try:
    from PyQt5.QtGui import QKeySequence
    from PyQt5.QtCore import QObject, pyqtSignal, QSettings, QTimer
    from PyQt5.QtWidgets import QWidget, QApplication, QShortcut
except ImportError as e:
    raise e


class ShortcutCategory(Enum):
    """Catégories de raccourcis."""
    FILE = "file"
    EDIT = "edit"
    VIEW = "view"
    ANNOTATION = "annotation"
    NAVIGATION = "navigation"
    TOOLS = "tools"
    HELP = "help"
    CUSTOM = "custom"


class ShortcutAction:
    """Représente une action de raccourci."""
    
    def __init__(self, id: str, name: str, description: str, 
                 default_key: str, category: ShortcutCategory,
                 callback: Callable = None, enabled: bool = True):
        self.id = id
        self.name = name
        self.description = description
        self.default_key = default_key
        self.category = category
        self.callback = callback
        self.enabled = enabled
        self.current_key = default_key
        self.shortcut_widget = None
        self.conflicts = []
    
    def set_key(self, new_key: str):
        """Définit la nouvelle touche de raccourci."""
        self.current_key = new_key
        if self.shortcut_widget:
            self.shortcut_widget.setKey(QKeySequence(new_key))
    
    def is_conflicted(self) -> bool:
        """Vérifie si le raccourci est en conflit."""
        return len(self.conflicts) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'default_key': self.default_key,
            'current_key': self.current_key,
            'category': self.category.value,
            'enabled': self.enabled,
            'conflicts': self.conflicts
        }


class ShortcutManager(QObject):
    """
    Gestionnaire de raccourcis personnalisables avec support des conflits.
    """
    
    # Signaux
    shortcutChanged = pyqtSignal(str, str)  # action_id, new_key
    shortcutConflict = pyqtSignal(str, list)  # action_id, conflicting_actions
    shortcutExecuted = pyqtSignal(str)  # action_id
    
    def __init__(self):
        super().__init__()
        
        self.actions: Dict[str, ShortcutAction] = {}
        self.shortcuts: Dict[str, QShortcut] = {}
        self.parent_widget = None
        
        # Configuration
        self.conflict_detection = True
        self.case_sensitive = False
        
        # Settings pour persistance
        self.settings = QSettings("AKOUMA", "Annotator")
        
        # Initialiser les raccourcis par défaut
        self._initialize_default_shortcuts()
        
        # Charger la configuration sauvegardée
        self._load_settings()
    
    def _initialize_default_shortcuts(self):
        """Initialise les raccourcis par défaut."""
        
        # Raccourcis de fichier
        self.add_action(
            "file.open", "Ouvrir fichier", "Ouvrir un fichier image",
            "Ctrl+O", ShortcutCategory.FILE
        )
        
        self.add_action(
            "file.open_dir", "Ouvrir dossier", "Ouvrir un dossier d'images",
            "Ctrl+U", ShortcutCategory.FILE
        )
        
        self.add_action(
            "file.save", "Sauvegarder", "Sauvegarder les annotations",
            "Ctrl+S", ShortcutCategory.FILE
        )
        
        self.add_action(
            "file.save_as", "Sauvegarder sous", "Sauvegarder sous un nouveau nom",
            "Ctrl+Shift+S", ShortcutCategory.FILE
        )
        
        self.add_action(
            "file.change_save_dir", "Changer dossier de sauvegarde", 
            "Changer le dossier de sauvegarde des annotations",
            "Ctrl+R", ShortcutCategory.FILE
        )
        
        self.add_action(
            "file.close", "Fermer", "Fermer l'application",
            "Ctrl+Q", ShortcutCategory.FILE
        )
        
        # Raccourcis d'édition
        self.add_action(
            "edit.undo", "Annuler", "Annuler la dernière action",
            "Ctrl+Z", ShortcutCategory.EDIT
        )
        
        self.add_action(
            "edit.redo", "Refaire", "Refaire la dernière action annulée",
            "Ctrl+Y", ShortcutCategory.EDIT
        )
        
        self.add_action(
            "edit.copy_shape", "Copier forme", "Copier la forme sélectionnée",
            "Ctrl+C", ShortcutCategory.EDIT
        )
        
        self.add_action(
            "edit.paste_shape", "Coller forme", "Coller la forme copiée",
            "Ctrl+V", ShortcutCategory.EDIT
        )
        
        self.add_action(
            "edit.delete_shape", "Supprimer forme", "Supprimer la forme sélectionnée",
            "Delete", ShortcutCategory.EDIT
        )
        
        self.add_action(
            "edit.select_all", "Tout sélectionner", "Sélectionner toutes les formes",
            "Ctrl+A", ShortcutCategory.EDIT
        )
        
        # Raccourcis de vue
        self.add_action(
            "view.zoom_in", "Zoom avant", "Zoomer sur l'image",
            "Ctrl++", ShortcutCategory.VIEW
        )
        
        self.add_action(
            "view.zoom_out", "Zoom arrière", "Dézoomer l'image",
            "Ctrl+-", ShortcutCategory.VIEW
        )
        
        self.add_action(
            "view.zoom_fit", "Ajuster à la fenêtre", "Ajuster l'image à la fenêtre",
            "Ctrl+0", ShortcutCategory.VIEW
        )
        
        self.add_action(
            "view.zoom_100", "Zoom 100%", "Zoom à 100%",
            "Ctrl+1", ShortcutCategory.VIEW
        )
        
        self.add_action(
            "view.toggle_labels", "Basculer étiquettes", "Afficher/masquer les étiquettes",
            "Ctrl+Shift+P", ShortcutCategory.VIEW
        )
        
        self.add_action(
            "view.toggle_dark_mode", "Mode sombre", "Basculer le mode sombre",
            "Ctrl+Shift+D", ShortcutCategory.VIEW
        )
        
        # Raccourcis d'annotation
        self.add_action(
            "annotation.create_rect", "Créer rectangle", "Créer un rectangle d'annotation",
            "W", ShortcutCategory.ANNOTATION
        )
        
        self.add_action(
            "annotation.create_polygon", "Créer polygone", "Créer un polygone d'annotation",
            "P", ShortcutCategory.ANNOTATION
        )
        
        self.add_action(
            "annotation.edit_label", "Éditer étiquette", "Éditer l'étiquette de la forme",
            "E", ShortcutCategory.ANNOTATION
        )
        
        self.add_action(
            "annotation.verify", "Vérifier", "Marquer l'image comme vérifiée",
            "Space", ShortcutCategory.ANNOTATION
        )
        
        self.add_action(
            "annotation.difficult", "Difficile", "Marquer la forme comme difficile",
            "D", ShortcutCategory.ANNOTATION
        )
        
        # Raccourcis de navigation
        self.add_action(
            "navigation.prev_image", "Image précédente", "Aller à l'image précédente",
            "A", ShortcutCategory.NAVIGATION
        )
        
        self.add_action(
            "navigation.next_image", "Image suivante", "Aller à l'image suivante",
            "D", ShortcutCategory.NAVIGATION
        )
        
        self.add_action(
            "navigation.first_image", "Première image", "Aller à la première image",
            "Home", ShortcutCategory.NAVIGATION
        )
        
        self.add_action(
            "navigation.last_image", "Dernière image", "Aller à la dernière image",
            "End", ShortcutCategory.NAVIGATION
        )
        
        self.add_action(
            "navigation.jump_to", "Aller à", "Aller à une image spécifique",
            "Ctrl+G", ShortcutCategory.NAVIGATION
        )
        
        # Raccourcis d'outils
        self.add_action(
            "tools.pan", "Panoramique", "Outil de panoramique",
            "H", ShortcutCategory.TOOLS
        )
        
        self.add_action(
            "tools.select", "Sélection", "Outil de sélection",
            "V", ShortcutCategory.TOOLS
        )
        
        self.add_action(
            "tools.zoom", "Zoom", "Outil de zoom",
            "Z", ShortcutCategory.TOOLS
        )
        
        self.add_action(
            "tools.brush", "Pinceau", "Outil de pinceau",
            "B", ShortcutCategory.TOOLS
        )
        
        # Raccourcis d'aide
        self.add_action(
            "help.shortcuts", "Raccourcis", "Afficher la liste des raccourcis",
            "F1", ShortcutCategory.HELP
        )
        
        self.add_action(
            "help.about", "À propos", "Afficher les informations sur l'application",
            "Ctrl+F1", ShortcutCategory.HELP
        )
        
        # Raccourcis numériques pour les classes (1-9)
        for i in range(1, 10):
            self.add_action(
                f"class.{i}", f"Classe {i}", f"Sélectionner la classe {i}",
                str(i), ShortcutCategory.CUSTOM
            )
    
    def set_parent_widget(self, widget: QWidget):
        """Définit le widget parent pour les raccourcis."""
        self.parent_widget = widget
        self._create_shortcuts()
    
    def add_action(self, action_id: str, name: str, description: str,
                   default_key: str, category: ShortcutCategory,
                   callback: Callable = None, enabled: bool = True) -> ShortcutAction:
        """Ajoute une nouvelle action de raccourci."""
        action = ShortcutAction(
            action_id, name, description, default_key, category, callback, enabled
        )
        self.actions[action_id] = action
        return action
    
    def remove_action(self, action_id: str) -> bool:
        """Supprime une action de raccourci."""
        if action_id in self.actions:
            # Supprimer le raccourci Qt
            if action_id in self.shortcuts:
                self.shortcuts[action_id].deleteLater()
                del self.shortcuts[action_id]
            
            del self.actions[action_id]
            return True
        return False
    
    def set_shortcut(self, action_id: str, new_key: str) -> bool:
        """Définit un nouveau raccourci pour une action."""
        if action_id not in self.actions:
            return False
        
        action = self.actions[action_id]
        
        # Vérifier les conflits
        if self.conflict_detection:
            conflicts = self._find_conflicts(new_key, action_id)
            if conflicts:
                action.conflicts = conflicts
                self.shortcutConflict.emit(action_id, conflicts)
                return False
            else:
                action.conflicts = []
        
        # Mettre à jour le raccourci
        action.set_key(new_key)
        
        # Recréer le raccourci Qt
        if self.parent_widget and action_id in self.shortcuts:
            self.shortcuts[action_id].deleteLater()
            self._create_shortcut(action_id)
        
        # Émettre le signal
        self.shortcutChanged.emit(action_id, new_key)
        
        return True
    
    def _find_conflicts(self, key: str, exclude_id: str = None) -> List[str]:
        """Trouve les actions en conflit avec une touche."""
        conflicts = []
        
        for action_id, action in self.actions.items():
            if action_id == exclude_id:
                continue
            
            if not self.case_sensitive:
                if key.lower() == action.current_key.lower():
                    conflicts.append(action_id)
            else:
                if key == action.current_key:
                    conflicts.append(action_id)
        
        return conflicts
    
    def _create_shortcuts(self):
        """Crée tous les raccourcis Qt."""
        if not self.parent_widget:
            return
        
        for action_id, action in self.actions.items():
            self._create_shortcut(action_id)
    
    def _create_shortcut(self, action_id: str):
        """Crée un raccourci Qt pour une action."""
        if not self.parent_widget or action_id not in self.actions:
            return
        
        action = self.actions[action_id]
        
        # Supprimer l'ancien raccourci
        if action_id in self.shortcuts:
            self.shortcuts[action_id].deleteLater()
        
        # Créer le nouveau raccourci
        shortcut = QShortcut(QKeySequence(action.current_key), self.parent_widget)
        shortcut.activated.connect(lambda: self._execute_action(action_id))
        
        self.shortcuts[action_id] = shortcut
        action.shortcut_widget = shortcut
    
    def _execute_action(self, action_id: str):
        """Exécute une action de raccourci."""
        if action_id not in self.actions:
            return
        
        action = self.actions[action_id]
        
        if not action.enabled:
            return
        
        # Émettre le signal
        self.shortcutExecuted.emit(action_id)
        
        # Exécuter le callback
        if action.callback:
            try:
                action.callback()
            except Exception as e:
                print(f"Erreur lors de l'exécution du raccourci {action_id}: {e}")
    
    def get_action(self, action_id: str) -> Optional[ShortcutAction]:
        """Retourne une action par son ID."""
        return self.actions.get(action_id)
    
    def get_actions_by_category(self, category: ShortcutCategory) -> List[ShortcutAction]:
        """Retourne toutes les actions d'une catégorie."""
        return [action for action in self.actions.values() if action.category == category]
    
    def get_all_actions(self) -> List[ShortcutAction]:
        """Retourne toutes les actions."""
        return list(self.actions.values())
    
    def enable_action(self, action_id: str, enabled: bool = True):
        """Active/désactive une action."""
        if action_id in self.actions:
            self.actions[action_id].enabled = enabled
            if action_id in self.shortcuts:
                self.shortcuts[action_id].setEnabled(enabled)
    
    def reset_to_defaults(self, category: Optional[ShortcutCategory] = None):
        """Remet les raccourcis aux valeurs par défaut."""
        actions_to_reset = self.actions.values()
        
        if category:
            actions_to_reset = [a for a in actions_to_reset if a.category == category]
        
        for action in actions_to_reset:
            self.set_shortcut(action.id, action.default_key)
    
    def export_shortcuts(self, file_path: str) -> bool:
        """Exporte les raccourcis vers un fichier JSON."""
        try:
            data = {
                'version': '1.0',
                'shortcuts': {}
            }
            
            for action_id, action in self.actions.items():
                data['shortcuts'][action_id] = {
                    'current_key': action.current_key,
                    'enabled': action.enabled
                }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Erreur lors de l'export des raccourcis: {e}")
            return False
    
    def import_shortcuts(self, file_path: str) -> bool:
        """Importe les raccourcis depuis un fichier JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'shortcuts' not in data:
                return False
            
            imported_count = 0
            for action_id, shortcut_data in data['shortcuts'].items():
                if action_id in self.actions:
                    action = self.actions[action_id]
                    
                    if 'current_key' in shortcut_data:
                        self.set_shortcut(action_id, shortcut_data['current_key'])
                        imported_count += 1
                    
                    if 'enabled' in shortcut_data:
                        self.enable_action(action_id, shortcut_data['enabled'])
            
            return imported_count > 0
        except Exception as e:
            print(f"Erreur lors de l'import des raccourcis: {e}")
            return False
    
    def _load_settings(self):
        """Charge la configuration depuis les settings."""
        shortcuts_data = self.settings.value("shortcuts/custom", {})
        
        for action_id, key in shortcuts_data.items():
            if action_id in self.actions:
                self.set_shortcut(action_id, key)
    
    def _save_settings(self):
        """Sauvegarde la configuration."""
        shortcuts_data = {}
        
        for action_id, action in self.actions.items():
            if action.current_key != action.default_key:
                shortcuts_data[action_id] = action.current_key
        
        self.settings.setValue("shortcuts/custom", shortcuts_data)
    
    def get_conflicts(self) -> Dict[str, List[str]]:
        """Retourne tous les conflits de raccourcis."""
        conflicts = {}
        
        for action_id, action in self.actions.items():
            if action.conflicts:
                conflicts[action_id] = action.conflicts
        
        return conflicts
    
    def resolve_conflict(self, action_id: str, new_key: str) -> bool:
        """Résout un conflit en changeant la touche."""
        return self.set_shortcut(action_id, new_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des raccourcis."""
        total_actions = len(self.actions)
        enabled_actions = sum(1 for a in self.actions.values() if a.enabled)
        custom_shortcuts = sum(1 for a in self.actions.values() 
                             if a.current_key != a.default_key)
        conflicts = len(self.get_conflicts())
        
        return {
            'total_actions': total_actions,
            'enabled_actions': enabled_actions,
            'custom_shortcuts': custom_shortcuts,
            'conflicts': conflicts,
            'categories': len(ShortcutCategory)
        }
    
    def shutdown(self):
        """Arrête le gestionnaire et sauvegarde la configuration."""
        self._save_settings()
        
        # Nettoyer les raccourcis
        for shortcut in self.shortcuts.values():
            shortcut.deleteLater()
        self.shortcuts.clear()


# Instance globale du gestionnaire de raccourcis
_shortcut_manager = None

def get_shortcut_manager() -> ShortcutManager:
    """Retourne l'instance globale du gestionnaire de raccourcis."""
    global _shortcut_manager
    if _shortcut_manager is None:
        _shortcut_manager = ShortcutManager()
    return _shortcut_manager
