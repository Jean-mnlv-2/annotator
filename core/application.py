#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Application principale - Point d'entrée centralisé de l'application.
"""

import sys
import os
from typing import Optional, Dict, Any

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    from PyQt4.QtWidgets import QApplication
    from PyQt4.QtCore import QObject, pyqtSignal

from .project_manager import ProjectManager
from .annotation_manager import AnnotationManager
from .config_manager import ConfigManager
from libs.image_cache import get_cache_manager
from libs.async_image_loader import get_async_loader
from libs.memory_manager import get_memory_manager
from libs.theme_manager import get_theme_manager
from libs.shortcut_manager import get_shortcut_manager
from libs.responsive_ui import get_responsive_manager
from libs.navigation_manager import get_navigation_manager


class Application(QObject):
    """
    Application principale qui coordonne tous les composants.
    """
    
    # Signaux
    applicationStarted = pyqtSignal()
    applicationClosing = pyqtSignal()
    projectOpened = pyqtSignal(str)  # project_path
    projectClosed = pyqtSignal()
    errorOccurred = pyqtSignal(str)  # error_message
    
    def __init__(self):
        super().__init__()
        
        # Composants principaux
        self.qt_app: Optional[QApplication] = None
        self.project_manager = ProjectManager()
        self.annotation_manager = AnnotationManager()
        self.config_manager = ConfigManager()
        
        # Gestionnaires de services
        self.cache_manager = get_cache_manager()
        self.async_loader = get_async_loader()
        self.memory_manager = get_memory_manager()
        self.theme_manager = get_theme_manager()
        self.shortcut_manager = get_shortcut_manager()
        self.responsive_manager = get_responsive_manager()
        self.navigation_manager = get_navigation_manager()
        
        # État de l'application
        self.is_initialized = False
        self.current_project_path: Optional[str] = None
        self.startup_time = None
        
        # Configuration
        self.debug_mode = False
        self.auto_save_enabled = True
        self.auto_save_interval = 300  # 5 minutes
        
        # Connecter les signaux
        self._connect_signals()
    
    def initialize(self, argv: list = None) -> bool:
        """
        Initialise l'application.
        
        Args:
            argv: Arguments de ligne de commande
            
        Returns:
            True si l'initialisation réussit
        """
        try:
            # Créer l'application Qt
            if not argv:
                argv = sys.argv
            
            self.qt_app = QApplication(argv)
            self.qt_app.setApplicationName("AKOUMA Annotator")
            self.qt_app.setApplicationVersion("2.0.0")
            self.qt_app.setOrganizationName("AKOUMA")
            
            # Configurer l'application Qt
            self._configure_qt_app()
            
            # Initialiser les gestionnaires
            self._initialize_managers()
            
            # Charger la configuration
            self.config_manager.load_config()
            
            # Appliquer la configuration
            self._apply_configuration()
            
            self.is_initialized = True
            self.startup_time = __import__('time').time()
            
            self.applicationStarted.emit()
            return True
            
        except Exception as e:
            self.errorOccurred.emit(f"Erreur lors de l'initialisation: {str(e)}")
            return False
    
    def _configure_qt_app(self):
        """Configure l'application Qt."""
        # Activer le support HiDPI
        self.qt_app.setAttribute(self.qt_app.AA_EnableHighDpiScaling, True)
        self.qt_app.setAttribute(self.qt_app.AA_UseHighDpiPixmaps, True)
        
        # Configurer les polices
        font = self.qt_app.font()
        font.setFamily("Segoe UI")
        font.setPointSize(9)
        self.qt_app.setFont(font)
        
        # Configurer le style
        if hasattr(self.qt_app, 'setStyleSheet'):
            self.qt_app.setStyleSheet("""
                QApplication {
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
            """)
    
    def _initialize_managers(self):
        """Initialise tous les gestionnaires."""
        # Configurer les gestionnaires
        self.shortcut_manager.set_parent_widget(self.qt_app)
        
        # Enregistrer les widgets responsive
        # (sera fait quand les widgets seront créés)
        
        # Configurer les callbacks de nettoyage
        self.memory_manager.register_cleanup_callback(self._cleanup_callback)
        
        # Connecter les signaux entre gestionnaires
        self._connect_manager_signals()
    
    def _connect_manager_signals(self):
        """Connecte les signaux entre gestionnaires."""
        # Thème -> Application
        self.theme_manager.themeChanged.connect(self._on_theme_changed)
        
        # Navigation -> Cache
        self.navigation_manager.currentImageChanged.connect(self._on_current_image_changed)
        
        # Mémoire -> Application
        self.memory_manager.memoryWarning.connect(self._on_memory_warning)
        self.memory_manager.memoryCritical.connect(self._on_memory_critical)
    
    def _apply_configuration(self):
        """Applique la configuration chargée."""
        config = self.config_manager.get_config()
        
        # Appliquer le thème
        theme_name = config.get('theme', {}).get('name', 'modern')
        theme_mode = config.get('theme', {}).get('mode', 'light')
        
        self.theme_manager.set_theme(theme_name)
        
        # Appliquer les raccourcis
        shortcuts = config.get('shortcuts', {})
        for action_id, key in shortcuts.items():
            self.shortcut_manager.set_shortcut(action_id, key)
        
        # Appliquer les paramètres de mémoire
        memory_config = config.get('memory', {})
        if memory_config:
            warning_threshold = memory_config.get('warning_threshold_mb', 800)
            critical_threshold = memory_config.get('critical_threshold_mb', 1200)
            self.memory_manager.set_thresholds(warning_threshold, critical_threshold)
        
        # Appliquer les paramètres de cache
        cache_config = config.get('cache', {})
        if cache_config:
            max_memory = cache_config.get('max_memory_mb', 500)
            max_items = cache_config.get('max_items', 100)
            self.cache_manager.set_memory_limit(max_memory)
            self.cache_manager.set_max_items(max_items)
    
    def _connect_signals(self):
        """Connecte les signaux internes."""
        self.applicationClosing.connect(self._on_application_closing)
    
    def run(self) -> int:
        """
        Lance l'application.
        
        Returns:
            Code de sortie de l'application
        """
        if not self.is_initialized:
            if not self.initialize():
                return 1
        
        try:
            return self.qt_app.exec_()
        except Exception as e:
            self.errorOccurred.emit(f"Erreur lors de l'exécution: {str(e)}")
            return 1
    
    def shutdown(self):
        """Arrête l'application proprement."""
        try:
            self.applicationClosing.emit()
            
            # Sauvegarder la configuration
            self.config_manager.save_config()
            
            # Arrêter tous les gestionnaires
            self._shutdown_managers()
            
            # Nettoyer les ressources
            self._cleanup_resources()
            
        except Exception as e:
            self.errorOccurred.emit(f"Erreur lors de l'arrêt: {str(e)}")
    
    def _shutdown_managers(self):
        """Arrête tous les gestionnaires."""
        self.cache_manager.clear_cache()
        self.async_loader.shutdown()
        self.memory_manager.shutdown()
        self.shortcut_manager.shutdown()
        self.responsive_manager.unregister_widget(self.qt_app)
        self.navigation_manager.shutdown()
    
    def _cleanup_resources(self):
        """Nettoie les ressources."""
        # Libérer la mémoire
        self.memory_manager.force_cleanup()
        
        # Nettoyer les caches
        self.cache_manager.clear_cache()
    
    def open_project(self, project_path: str) -> bool:
        """
        Ouvre un projet.
        
        Args:
            project_path: Chemin vers le projet
            
        Returns:
            True si le projet est ouvert avec succès
        """
        try:
            if self.project_manager.open_project(project_path):
                self.current_project_path = project_path
                
                # Configurer les gestionnaires pour le projet
                self._configure_project_managers()
                
                self.projectOpened.emit(project_path)
                return True
            
            return False
            
        except Exception as e:
            self.errorOccurred.emit(f"Erreur lors de l'ouverture du projet: {str(e)}")
            return False
    
    def close_project(self):
        """Ferme le projet actuel."""
        try:
            if self.current_project_path:
                self.project_manager.close_project()
                self.current_project_path = None
                self.projectClosed.emit()
                
        except Exception as e:
            self.errorOccurred.emit(f"Erreur lors de la fermeture du projet: {str(e)}")
    
    def _configure_project_managers(self):
        """Configure les gestionnaires pour le projet actuel."""
        if not self.current_project_path:
            return
        
        # Configurer le gestionnaire de navigation
        image_paths = self.project_manager.get_image_paths()
        if image_paths:
            self.navigation_manager.set_image_list(image_paths)
        
        # Configurer le gestionnaire d'annotations
        annotation_dir = self.project_manager.get_annotation_directory()
        if annotation_dir:
            self.annotation_manager.set_annotation_directory(annotation_dir)
    
    def get_application_info(self) -> Dict[str, Any]:
        """Retourne les informations sur l'application."""
        import platform
        
        return {
            'name': 'AKOUMA Annotator',
            'version': '2.0.0',
            'platform': platform.system(),
            'python_version': sys.version,
            'qt_version': self.qt_app.applicationVersion() if self.qt_app else 'Unknown',
            'startup_time': self.startup_time,
            'is_initialized': self.is_initialized,
            'current_project': self.current_project_path,
            'debug_mode': self.debug_mode
        }
    
    def get_managers_status(self) -> Dict[str, Any]:
        """Retourne l'état de tous les gestionnaires."""
        return {
            'cache_manager': self.cache_manager.get_cache_stats(),
            'memory_manager': self.memory_manager.get_memory_stats(),
            'theme_manager': self.theme_manager.get_theme_info(),
            'shortcut_manager': self.shortcut_manager.get_stats(),
            'responsive_manager': self.responsive_manager.get_stats(),
            'navigation_manager': self.navigation_manager.get_navigation_stats()
        }
    
    # Callbacks et slots
    def _on_theme_changed(self, theme_name: str, mode: str):
        """Callback pour le changement de thème."""
        # Sauvegarder la configuration
        config = self.config_manager.get_config()
        config['theme'] = {'name': theme_name, 'mode': mode}
        self.config_manager.set_config(config)
    
    def _on_current_image_changed(self, image_info):
        """Callback pour le changement d'image."""
        # Précharger les images suivantes
        if hasattr(image_info, 'path'):
            # Logique de préchargement
            pass
    
    def _on_memory_warning(self, message: str):
        """Callback pour l'avertissement mémoire."""
        print(f"Avertissement mémoire: {message}")
        # Ici on pourrait afficher une notification à l'utilisateur
    
    def _on_memory_critical(self, message: str):
        """Callback pour la mémoire critique."""
        print(f"Mémoire critique: {message}")
        # Ici on pourrait forcer un nettoyage d'urgence
    
    def _on_application_closing(self):
        """Callback pour la fermeture de l'application."""
        # Sauvegarder l'état actuel
        if self.current_project_path:
            self.project_manager.save_project()
    
    def _cleanup_callback(self, emergency: bool = False) -> int:
        """Callback de nettoyage pour le gestionnaire de mémoire."""
        freed_mb = 0
        
        # Nettoyer le cache d'images
        if emergency:
            self.cache_manager.clear_cache()
            freed_mb += 100  # Estimation
        
        # Nettoyer les caches temporaires
        # (implémentation spécifique selon les besoins)
        
        return freed_mb


# Instance globale de l'application
_app_instance = None

def get_application() -> Application:
    """Retourne l'instance globale de l'application."""
    global _app_instance
    if _app_instance is None:
        _app_instance = Application()
    return _app_instance
