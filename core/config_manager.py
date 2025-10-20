#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gestionnaire de configuration - Gère la configuration de l'application.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from PyQt5.QtCore import QObject, pyqtSignal, QSettings
except ImportError:
    from PyQt4.QtCore import QObject, pyqtSignal, QSettings


class ConfigManager(QObject):
    """
    Gestionnaire de configuration pour l'application.
    """
    
    # Signaux
    configChanged = pyqtSignal(str, Any)  # key, value
    configLoaded = pyqtSignal()
    configSaved = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Configuration par défaut
        self.default_config = {
            'application': {
                'name': 'AKOUMA Annotator',
                'version': '2.0.0',
                'language': 'fr',
                'auto_save': True,
                'auto_save_interval': 300,
                'backup_enabled': True,
                'debug_mode': False
            },
            'theme': {
                'name': 'modern',
                'mode': 'light',
                'animations_enabled': True,
                'auto_switch': True
            },
            'shortcuts': {
                # Les raccourcis par défaut seront chargés depuis le gestionnaire
            },
            'memory': {
                'warning_threshold_mb': 800,
                'critical_threshold_mb': 1200,
                'auto_cleanup': True,
                'cleanup_interval': 300
            },
            'cache': {
                'max_memory_mb': 500,
                'max_items': 100,
                'preload_enabled': True,
                'preload_count': 3
            },
            'navigation': {
                'mode': 'sequential',
                'loop_mode': False,
                'auto_advance': False,
                'smart_navigation': True
            },
            'ui': {
                'responsive_enabled': True,
                'auto_optimize': True,
                'animation_duration': 300,
                'dock_areas': ['left', 'right', 'bottom']
            },
            'annotations': {
                'default_format': 'pascal_voc',
                'auto_save': True,
                'backup_enabled': True,
                'compression_enabled': True
            },
            'recent': {
                'max_projects': 10,
                'max_files': 20
            }
        }
        
        # Configuration actuelle
        self.config = self.default_config.copy()
        
        # Settings Qt
        self.settings = QSettings("AKOUMA", "Annotator")
        
        # État
        self.is_loaded = False
        self.is_dirty = False
        self.last_save_time = None
        
        # Chemin du fichier de configuration
        self.config_file_path = self._get_config_file_path()
    
    def _get_config_file_path(self) -> str:
        """Retourne le chemin du fichier de configuration."""
        # Utiliser le dossier de configuration de l'utilisateur
        config_dir = os.path.expanduser("~/.config/AKOUMA")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "annotator_config.json")
    
    def load_config(self, config_file: str = None) -> bool:
        """
        Charge la configuration depuis le fichier.
        
        Args:
            config_file: Chemin vers le fichier de configuration (optionnel)
            
        Returns:
            True si la configuration est chargée avec succès
        """
        try:
            if config_file:
                self.config_file_path = config_file
            
            # Charger depuis le fichier JSON si il existe
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                
                # Fusionner avec la configuration par défaut
                self.config = self._merge_config(self.default_config, file_config)
            
            # Charger depuis les settings Qt pour les paramètres sensibles
            self._load_qt_settings()
            
            self.is_loaded = True
            self.is_dirty = False
            self.configLoaded.emit()
            return True
            
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration: {e}")
            # Utiliser la configuration par défaut en cas d'erreur
            self.config = self.default_config.copy()
            self.is_loaded = True
            return False
    
    def save_config(self, config_file: str = None) -> bool:
        """
        Sauvegarde la configuration dans le fichier.
        
        Args:
            config_file: Chemin vers le fichier de configuration (optionnel)
            
        Returns:
            True si la configuration est sauvegardée avec succès
        """
        try:
            if config_file:
                self.config_file_path = config_file
            
            # Créer le dossier si nécessaire
            config_dir = os.path.dirname(self.config_file_path)
            os.makedirs(config_dir, exist_ok=True)
            
            # Sauvegarder dans le fichier JSON
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            # Sauvegarder dans les settings Qt
            self._save_qt_settings()
            
            self.is_dirty = False
            self.last_save_time = datetime.now().isoformat()
            self.configSaved.emit()
            return True
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration: {e}")
            return False
    
    def _merge_config(self, default: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
        """Fusionne deux configurations."""
        merged = default.copy()
        
        for key, value in custom.items():
            if key in merged:
                if isinstance(value, dict) and isinstance(merged[key], dict):
                    merged[key] = self._merge_config(merged[key], value)
                else:
                    merged[key] = value
            else:
                merged[key] = value
        
        return merged
    
    def _load_qt_settings(self):
        """Charge les paramètres depuis les settings Qt."""
        # Paramètres sensibles ou spécifiques à Qt
        qt_keys = [
            'application/language',
            'theme/mode',
            'memory/warning_threshold_mb',
            'memory/critical_threshold_mb'
        ]
        
        for key in qt_keys:
            value = self.settings.value(key)
            if value is not None:
                self._set_nested_value(key, value)
    
    def _save_qt_settings(self):
        """Sauvegarde les paramètres dans les settings Qt."""
        # Sauvegarder les paramètres sensibles
        qt_mappings = {
            'application.language': 'application/language',
            'theme.mode': 'theme/mode',
            'memory.warning_threshold_mb': 'memory/warning_threshold_mb',
            'memory.critical_threshold_mb': 'memory/critical_threshold_mb'
        }
        
        for config_key, qt_key in qt_mappings.items():
            value = self._get_nested_value(config_key)
            if value is not None:
                self.settings.setValue(qt_key, value)
    
    def get_config(self) -> Dict[str, Any]:
        """Retourne la configuration complète."""
        return self.config.copy()
    
    def set_config(self, config: Dict[str, Any]):
        """Définit la configuration complète."""
        self.config = config.copy()
        self.is_dirty = True
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration.
        
        Args:
            key: Clé de configuration (ex: 'theme.mode')
            default: Valeur par défaut
            
        Returns:
            Valeur de configuration
        """
        return self._get_nested_value(key, default)
    
    def set_value(self, key: str, value: Any):
        """
        Définit une valeur de configuration.
        
        Args:
            key: Clé de configuration (ex: 'theme.mode')
            value: Nouvelle valeur
        """
        old_value = self._get_nested_value(key)
        self._set_nested_value(key, value)
        
        if old_value != value:
            self.is_dirty = True
            self.configChanged.emit(key, value)
    
    def _get_nested_value(self, key: str, default: Any = None) -> Any:
        """Récupère une valeur imbriquée."""
        keys = key.split('.')
        current = self.config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def _set_nested_value(self, key: str, value: Any):
        """Définit une valeur imbriquée."""
        keys = key.split('.')
        current = self.config
        
        # Naviguer jusqu'au niveau parent
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Définir la valeur
        current[keys[-1]] = value
    
    def reset_to_defaults(self, section: str = None):
        """
        Remet la configuration aux valeurs par défaut.
        
        Args:
            section: Section à réinitialiser (None pour tout réinitialiser)
        """
        if section is None:
            self.config = self.default_config.copy()
        else:
            if section in self.default_config:
                self.config[section] = self.default_config[section].copy()
        
        self.is_dirty = True
    
    def export_config(self, export_path: str) -> bool:
        """
        Exporte la configuration vers un fichier.
        
        Args:
            export_path: Chemin du fichier d'export
            
        Returns:
            True si l'export réussit
        """
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erreur lors de l'export de la configuration: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """
        Importe la configuration depuis un fichier.
        
        Args:
            import_path: Chemin du fichier d'import
            
        Returns:
            True si l'import réussit
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # Fusionner avec la configuration actuelle
            self.config = self._merge_config(self.config, imported_config)
            self.is_dirty = True
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'import de la configuration: {e}")
            return False
    
    def validate_config(self) -> Dict[str, List[str]]:
        """
        Valide la configuration et retourne les erreurs.
        
        Returns:
            Dictionnaire des erreurs par section
        """
        errors = {}
        
        # Validation des valeurs numériques
        numeric_validations = {
            'memory.warning_threshold_mb': (100, 2000),
            'memory.critical_threshold_mb': (500, 4000),
            'cache.max_memory_mb': (50, 2000),
            'cache.max_items': (10, 1000),
            'application.auto_save_interval': (30, 3600)
        }
        
        for key, (min_val, max_val) in numeric_validations.items():
            value = self.get_value(key)
            if value is not None:
                if not isinstance(value, (int, float)) or not (min_val <= value <= max_val):
                    section = key.split('.')[0]
                    if section not in errors:
                        errors[section] = []
                    errors[section].append(f"{key} doit être entre {min_val} et {max_val}")
        
        # Validation des valeurs booléennes
        boolean_keys = [
            'application.auto_save',
            'application.backup_enabled',
            'theme.animations_enabled',
            'cache.preload_enabled'
        ]
        
        for key in boolean_keys:
            value = self.get_value(key)
            if value is not None and not isinstance(value, bool):
                section = key.split('.')[0]
                if section not in errors:
                    errors[section] = []
                errors[section].append(f"{key} doit être un booléen")
        
        # Validation des valeurs énumérées
        enum_validations = {
            'theme.mode': ['light', 'dark', 'auto'],
            'annotations.default_format': ['pascal_voc', 'yolo', 'coco', 'createml'],
            'navigation.mode': ['sequential', 'random', 'filtered', 'smart']
        }
        
        for key, valid_values in enum_validations.items():
            value = self.get_value(key)
            if value is not None and value not in valid_values:
                section = key.split('.')[0]
                if section not in errors:
                    errors[section] = []
                errors[section].append(f"{key} doit être l'une des valeurs: {', '.join(valid_values)}")
        
        return errors
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Retourne une section de la configuration.
        
        Args:
            section: Nom de la section
            
        Returns:
            Configuration de la section
        """
        return self.config.get(section, {}).copy()
    
    def set_section(self, section: str, config: Dict[str, Any]):
        """
        Définit une section de la configuration.
        
        Args:
            section: Nom de la section
            config: Configuration de la section
        """
        self.config[section] = config.copy()
        self.is_dirty = True
    
    def has_key(self, key: str) -> bool:
        """Vérifie si une clé existe dans la configuration."""
        return self._get_nested_value(key) is not None
    
    def remove_key(self, key: str) -> bool:
        """Supprime une clé de la configuration."""
        keys = key.split('.')
        current = self.config
        
        try:
            for k in keys[:-1]:
                current = current[k]
            
            if keys[-1] in current:
                del current[keys[-1]]
                self.is_dirty = True
                return True
            return False
            
        except (KeyError, TypeError):
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """Retourne les informations sur la configuration."""
        return {
            'config_file_path': self.config_file_path,
            'is_loaded': self.is_loaded,
            'is_dirty': self.is_dirty,
            'last_save_time': self.last_save_time,
            'sections': list(self.config.keys()),
            'total_keys': self._count_keys(self.config)
        }
    
    def _count_keys(self, config: Dict[str, Any], prefix: str = "") -> int:
        """Compte le nombre total de clés dans la configuration."""
        count = 0
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                count += self._count_keys(value, full_key)
            else:
                count += 1
        return count
    
    def backup_config(self, backup_path: str = None) -> bool:
        """
        Crée une sauvegarde de la configuration.
        
        Args:
            backup_path: Chemin de la sauvegarde (optionnel)
            
        Returns:
            True si la sauvegarde réussit
        """
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{self.config_file_path}.backup_{timestamp}"
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration: {e}")
            return False
    
    def restore_config(self, backup_path: str) -> bool:
        """
        Restaure la configuration depuis une sauvegarde.
        
        Args:
            backup_path: Chemin de la sauvegarde
            
        Returns:
            True si la restauration réussit
        """
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_config = json.load(f)
            
            self.config = backup_config
            self.is_dirty = True
            return True
            
        except Exception as e:
            print(f"Erreur lors de la restauration de la configuration: {e}")
            return False
