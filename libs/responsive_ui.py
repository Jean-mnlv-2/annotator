#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

try:
    from PyQt5.QtGui import QFont, QFontMetrics, QResizeEvent
    from PyQt5.QtCore import QObject, pyqtSignal, QSize, QRect, QTimer, QPropertyAnimation, QEasingCurve
    from PyQt5.QtWidgets import (QWidget, QMainWindow, QDockWidget, QSplitter, 
                                QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy,
                                QApplication, QScrollArea, QFrame)
except ImportError:
    from PyQt4.QtGui import QFont, QFontMetrics, QResizeEvent, QWidget, QMainWindow, QDockWidget, QSplitter
    from PyQt4.QtCore import QObject, pyqtSignal, QSize, QRect, QTimer, QPropertyAnimation, QEasingCurve
    from PyQt4.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy, QApplication, QScrollArea, QFrame


class Breakpoint(Enum):
    """Points de rupture pour le responsive design."""
    XS = "xs"      # < 480px
    SM = "sm"      # 480px - 768px
    MD = "md"      # 768px - 1024px
    LG = "lg"      # 1024px - 1440px
    XL = "xl"      # > 1440px


class ResponsiveConfig:
    """Configuration responsive pour un composant."""
    
    def __init__(self):
        self.breakpoints = {
            Breakpoint.XS: {'min_width': 0, 'max_width': 479},
            Breakpoint.SM: {'min_width': 480, 'max_width': 767},
            Breakpoint.MD: {'min_width': 768, 'max_width': 1023},
            Breakpoint.LG: {'min_width': 1024, 'max_width': 1439},
            Breakpoint.XL: {'min_width': 1440, 'max_width': float('inf')}
        }
        
        # Configuration par défaut
        self.default_config = {
            'layout': 'horizontal',  # horizontal, vertical, grid
            'columns': 1,
            'spacing': 8,
            'margins': (8, 8, 8, 8),
            'min_size': (200, 150),
            'max_size': (1920, 1080),
            'dock_areas': ['left', 'right', 'bottom'],
            'collapsible': True,
            'resizable': True
        }
        
        # Configuration par breakpoint
        self.breakpoint_configs = {
            Breakpoint.XS: {
                'layout': 'vertical',
                'columns': 1,
                'spacing': 4,
                'margins': (4, 4, 4, 4),
                'dock_areas': ['bottom'],
                'collapsible': True
            },
            Breakpoint.SM: {
                'layout': 'vertical',
                'columns': 1,
                'spacing': 6,
                'margins': (6, 6, 6, 6),
                'dock_areas': ['left', 'bottom']
            },
            Breakpoint.MD: {
                'layout': 'horizontal',
                'columns': 2,
                'spacing': 8,
                'margins': (8, 8, 8, 8),
                'dock_areas': ['left', 'right', 'bottom']
            },
            Breakpoint.LG: {
                'layout': 'horizontal',
                'columns': 3,
                'spacing': 10,
                'margins': (10, 10, 10, 10),
                'dock_areas': ['left', 'right', 'bottom']
            },
            Breakpoint.XL: {
                'layout': 'horizontal',
                'columns': 4,
                'spacing': 12,
                'margins': (12, 12, 12, 12),
                'dock_areas': ['left', 'right', 'bottom', 'top']
            }
        }
    
    def get_config(self, breakpoint: Breakpoint) -> Dict[str, Any]:
        """Retourne la configuration pour un breakpoint."""
        config = self.default_config.copy()
        if breakpoint in self.breakpoint_configs:
            config.update(self.breakpoint_configs[breakpoint])
        return config
    
    def get_breakpoint(self, width: int) -> Breakpoint:
        """Détermine le breakpoint selon la largeur."""
        for bp in Breakpoint:
            bp_config = self.breakpoints[bp]
            if bp_config['min_width'] <= width <= bp_config['max_width']:
                return bp
        return Breakpoint.XL


class ResponsiveWidget(QWidget):
    """Widget responsive de base."""
    
    # Signaux
    breakpointChanged = pyqtSignal(Breakpoint)
    layoutChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config = ResponsiveConfig()
        self.current_breakpoint = Breakpoint.MD
        self.last_size = QSize()
        
        # Timer pour éviter les mises à jour trop fréquentes
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._on_resize_timeout)
        
        # Configuration
        self.auto_layout = True
        self.animations_enabled = True
        
        # Historique des tailles pour détecter les changements significatifs
        self.size_history = []
    
    def resizeEvent(self, event: QResizeEvent):
        """Gère le redimensionnement."""
        super().resizeEvent(event)
        
        new_size = event.size()
        if new_size != self.last_size:
            self.last_size = new_size
            self.resize_timer.start(150)  # Attendre 150ms avant de traiter
    
    def _on_resize_timeout(self):
        """Traite le redimensionnement après le délai."""
        self._update_breakpoint()
        self._update_layout()
    
    def _update_breakpoint(self):
        """Met à jour le breakpoint actuel."""
        width = self.width()
        new_breakpoint = self.config.get_breakpoint(width)
        
        if new_breakpoint != self.current_breakpoint:
            self.current_breakpoint = new_breakpoint
            self.breakpointChanged.emit(new_breakpoint)
    
    def _update_layout(self):
        """Met à jour la mise en page selon le breakpoint."""
        if not self.auto_layout:
            return
        
        config = self.config.get_config(self.current_breakpoint)
        self._apply_layout_config(config)
        self.layoutChanged.emit(config['layout'])
    
    def _apply_layout_config(self, config: Dict[str, Any]):
        """Applique la configuration de mise en page."""
        # Implémentation spécifique à chaque widget
        pass
    
    def get_current_config(self) -> Dict[str, Any]:
        """Retourne la configuration actuelle."""
        return self.config.get_config(self.current_breakpoint)


class ResponsiveDockWidget(QDockWidget):
    """Widget dock responsive."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        
        self.responsive_config = ResponsiveConfig()
        self.current_breakpoint = Breakpoint.MD
        self.original_size = None
        
        # Configuration
        self.auto_hide = False
        self.minimized_width = 40
        self.animation_duration = 200
        
        # Timer pour les animations
        self.animation_timer = QTimer()
        self.animation_timer.setSingleShot(True)
    
    def set_responsive_config(self, config: ResponsiveConfig):
        """Définit la configuration responsive."""
        self.responsive_config = config
    
    def update_for_breakpoint(self, breakpoint: Breakpoint):
        """Met à jour le widget pour un breakpoint."""
        self.current_breakpoint = breakpoint
        config = self.responsive_config.get_config(breakpoint)
        
        # Adapter la taille
        self._adapt_size(config)
        
        # Adapter la position
        self._adapt_position(config)
        
        # Adapter la visibilité
        self._adapt_visibility(config)
    
    def _adapt_size(self, config: Dict[str, Any]):
        """Adapte la taille du widget."""
        if 'min_size' in config:
            min_size = config['min_size']
            self.setMinimumSize(min_size[0], min_size[1])
        
        if 'max_size' in config:
            max_size = config['max_size']
            self.setMaximumSize(max_size[0], max_size[1])
    
    def _adapt_position(self, config: Dict[str, Any]):
        """Adapte la position du widget."""
        if 'dock_areas' in config:
            # Logique pour adapter les zones de dock selon le breakpoint
            pass
    
    def _adapt_visibility(self, config: Dict[str, Any]):
        """Adapte la visibilité du widget."""
        if self.auto_hide and self.current_breakpoint in [Breakpoint.XS, Breakpoint.SM]:
            self.setFloating(False)
            # Réduire à une barre mince
            self.resize(self.minimized_width, self.height())


class ResponsiveMainWindow(QMainWindow):
    """Fenêtre principale responsive."""
    
    # Signaux
    layoutOptimized = pyqtSignal(Breakpoint)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.responsive_config = ResponsiveConfig()
        self.current_breakpoint = Breakpoint.MD
        self.dock_widgets = {}
        self.splitter = None
        
        # Configuration
        self.auto_optimize = True
        self.preserve_layout = True
        self.animation_enabled = True
        
        # Timer pour les optimisations
        self.optimize_timer = QTimer()
        self.optimize_timer.setSingleShot(True)
        self.optimize_timer.timeout.connect(self._optimize_layout)
        
        # Historique des layouts
        self.layout_history = []
        
        # Configuration des animations
        self.animation_duration = 300
        self.animation_easing = QEasingCurve.OutCubic
    
    def add_responsive_dock(self, widget: QWidget, title: str, area: int, 
                           config: Optional[ResponsiveConfig] = None) -> ResponsiveDockWidget:
        """Ajoute un widget dock responsive."""
        dock = ResponsiveDockWidget(title, self)
        dock.setWidget(widget)
        
        if config:
            dock.set_responsive_config(config)
        
        self.addDockWidget(area, dock)
        self.dock_widgets[title] = dock
        
        return dock
    
    def resizeEvent(self, event):
        """Gère le redimensionnement de la fenêtre."""
        super().resizeEvent(event)
        
        # Détecter le nouveau breakpoint
        width = event.size().width()
        new_breakpoint = self.responsive_config.get_breakpoint(width)
        
        if new_breakpoint != self.current_breakpoint:
            self.current_breakpoint = new_breakpoint
            self._update_layout_for_breakpoint(new_breakpoint)
        
        # Programmer l'optimisation du layout
        if self.auto_optimize:
            self.optimize_timer.start(200)
    
    def _update_layout_for_breakpoint(self, breakpoint: Breakpoint):
        """Met à jour la mise en page pour un breakpoint."""
        config = self.responsive_config.get_config(breakpoint)
        
        # Mettre à jour tous les docks
        for dock in self.dock_widgets.values():
            dock.update_for_breakpoint(breakpoint)
        
        # Adapter les splitters
        self._adapt_splitters(config)
        
        # Adapter la barre d'outils
        self._adapt_toolbars(config)
        
        # Émettre le signal
        self.layoutOptimized.emit(breakpoint)
    
    def _adapt_splitters(self, config: Dict[str, Any]):
        """Adapte les splitters selon la configuration."""
        if self.splitter:
            if config['layout'] == 'vertical':
                self.splitter.setOrientation(1)  # Qt.Vertical
            else:
                self.splitter.setOrientation(0)  # Qt.Horizontal
    
    def _adapt_toolbars(self, config: Dict[str, Any]):
        """Adapte les barres d'outils."""
        toolbars = self.findChildren(QWidget)
        
        for toolbar in toolbars:
            if hasattr(toolbar, 'setToolButtonStyle'):
                if self.current_breakpoint in [Breakpoint.XS, Breakpoint.SM]:
                    # Style compact pour petits écrans
                    toolbar.setToolButtonStyle(1)  # Qt.ToolButtonIconOnly
                else:
                    # Style normal pour grands écrans
                    toolbar.setToolButtonStyle(2)  # Qt.ToolButtonTextUnderIcon
    
    def _optimize_layout(self):
        """Optimise la mise en page."""
        # Calculer les ratios optimaux
        optimal_ratios = self._calculate_optimal_ratios()
        
        # Appliquer les ratios
        if self.splitter and optimal_ratios:
            self.splitter.setSizes(optimal_ratios)
        
        # Sauvegarder le layout
        if self.preserve_layout:
            self._save_layout_state()
    
    def _calculate_optimal_ratios(self) -> List[int]:
        """Calcule les ratios optimaux pour les splitters."""
        config = self.responsive_config.get_config(self.current_breakpoint)
        
        if config['layout'] == 'vertical':
            # Plus d'espace pour le contenu principal
            return [300, 700]
        else:
            # Équilibre entre les panneaux
            return [400, 600]
    
    def _save_layout_state(self):
        """Sauvegarde l'état du layout."""
        state = self.saveState()
        self.layout_history.append({
            'breakpoint': self.current_breakpoint.value,
            'state': state,
            'timestamp': QTimer.singleShot(0, lambda: None)
        })
        
        # Limiter l'historique
        if len(self.layout_history) > 10:
            self.layout_history.pop(0)
    
    def restore_layout_state(self, breakpoint: Breakpoint) -> bool:
        """Restaure l'état du layout pour un breakpoint."""
        for layout_data in reversed(self.layout_history):
            if layout_data['breakpoint'] == breakpoint.value:
                self.restoreState(layout_data['state'])
                return True
        return False
    
    def set_responsive_config(self, config: ResponsiveConfig):
        """Définit la configuration responsive."""
        self.responsive_config = config
    
    def get_current_breakpoint(self) -> Breakpoint:
        """Retourne le breakpoint actuel."""
        return self.current_breakpoint
    
    def get_layout_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du layout."""
        return {
            'current_breakpoint': self.current_breakpoint.value,
            'dock_widgets_count': len(self.dock_widgets),
            'layout_history_count': len(self.layout_history),
            'window_size': (self.width(), self.height()),
            'auto_optimize': self.auto_optimize,
            'animation_enabled': self.animation_enabled
        }


class ResponsiveSplitter(QSplitter):
    """Splitter responsive."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.responsive_config = ResponsiveConfig()
        self.current_breakpoint = Breakpoint.MD
        self.minimum_sizes = {}
        self.maximum_sizes = {}
        
        # Configuration
        self.auto_resize = True
        self.preserve_proportions = True
    
    def set_responsive_config(self, config: ResponsiveConfig):
        """Définit la configuration responsive."""
        self.responsive_config = config
    
    def update_for_breakpoint(self, breakpoint: Breakpoint):
        """Met à jour le splitter pour un breakpoint."""
        self.current_breakpoint = breakpoint
        config = self.responsive_config.get_config(breakpoint)
        
        # Adapter l'orientation
        if config['layout'] == 'vertical':
            self.setOrientation(1)  # Qt.Vertical
        else:
            self.setOrientation(0)  # Qt.Horizontal
        
        # Adapter les tailles
        self._adapt_sizes(config)
    
    def _adapt_sizes(self, config: Dict[str, Any]):
        """Adapte les tailles des widgets."""
        if not self.auto_resize:
            return
        
        # Définir les tailles minimales et maximales
        for i in range(self.count()):
            widget = self.widget(i)
            if widget:
                if 'min_size' in config:
                    min_size = config['min_size']
                    widget.setMinimumSize(min_size[0], min_size[1])
                
                if 'max_size' in config:
                    max_size = config['max_size']
                    widget.setMaximumSize(max_size[0], max_size[1])


class ResponsiveGridLayout(QGridLayout):
    """Layout en grille responsive."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.responsive_config = ResponsiveConfig()
        self.current_breakpoint = Breakpoint.MD
        
        # Configuration
        self.auto_columns = True
        self.equal_widths = True
    
    def update_for_breakpoint(self, breakpoint: Breakpoint):
        """Met à jour le layout pour un breakpoint."""
        self.current_breakpoint = breakpoint
        config = self.responsive_config.get_config(breakpoint)
        
        # Adapter le nombre de colonnes
        if self.auto_columns:
            self._adapt_columns(config['columns'])
        
        # Adapter l'espacement
        spacing = config.get('spacing', 8)
        self.setSpacing(spacing)
        
        # Adapter les marges
        margins = config.get('margins', (8, 8, 8, 8))
        self.setContentsMargins(*margins)
    
    def _adapt_columns(self, columns: int):
        """Adapte le nombre de colonnes."""
        current_columns = self.columnCount()
        
        if columns != current_columns:
            # Réorganiser les widgets selon le nouveau nombre de colonnes
            widgets = []
            
            # Collecter tous les widgets
            for i in range(self.count()):
                item = self.itemAt(i)
                if item and item.widget():
                    widgets.append(item.widget())
            
            # Vider le layout
            self.clear()
            
            # Réorganiser selon le nouveau nombre de colonnes
            for i, widget in enumerate(widgets):
                row = i // columns
                col = i % columns
                self.addWidget(widget, row, col)


class ResponsiveManager(QObject):
    """Gestionnaire central pour le responsive design."""
    
    # Signaux
    globalBreakpointChanged = pyqtSignal(Breakpoint)
    layoutOptimized = pyqtSignal(Breakpoint)
    
    def __init__(self):
        super().__init__()
        
        self.responsive_config = ResponsiveConfig()
        self.current_breakpoint = Breakpoint.MD
        self.managed_widgets = []
        
        # Configuration globale
        self.auto_optimize = True
        self.animation_enabled = True
        self.breakpoint_detection = True
        
        # Timer pour les optimisations globales
        self.global_timer = QTimer()
        self.global_timer.timeout.connect(self._global_optimize)
        self.global_timer.start(5000)  # Optimiser toutes les 5 secondes
    
    def register_widget(self, widget: QWidget):
        """Enregistre un widget pour la gestion responsive."""
        if widget not in self.managed_widgets:
            self.managed_widgets.append(widget)
    
    def unregister_widget(self, widget: QWidget):
        """Désenregistre un widget."""
        if widget in self.managed_widgets:
            self.managed_widgets.remove(widget)
    
    def update_breakpoint(self, width: int):
        """Met à jour le breakpoint global."""
        new_breakpoint = self.responsive_config.get_breakpoint(width)
        
        if new_breakpoint != self.current_breakpoint:
            self.current_breakpoint = new_breakpoint
            self.globalBreakpointChanged.emit(new_breakpoint)
            
            # Mettre à jour tous les widgets enregistrés
            self._update_all_widgets(new_breakpoint)
    
    def _update_all_widgets(self, breakpoint: Breakpoint):
        """Met à jour tous les widgets enregistrés."""
        for widget in self.managed_widgets:
            if hasattr(widget, 'update_for_breakpoint'):
                widget.update_for_breakpoint(breakpoint)
            elif hasattr(widget, '_update_breakpoint'):
                widget._update_breakpoint()
    
    def _global_optimize(self):
        """Optimisation globale périodique."""
        if self.auto_optimize:
            self.layoutOptimized.emit(self.current_breakpoint)
    
    def get_current_breakpoint(self) -> Breakpoint:
        """Retourne le breakpoint actuel."""
        return self.current_breakpoint
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du gestionnaire."""
        return {
            'current_breakpoint': self.current_breakpoint.value,
            'managed_widgets': len(self.managed_widgets),
            'auto_optimize': self.auto_optimize,
            'animation_enabled': self.animation_enabled,
            'breakpoint_detection': self.breakpoint_detection
        }


# Instance globale du gestionnaire responsive
_responsive_manager = None

def get_responsive_manager() -> ResponsiveManager:
    """Retourne l'instance globale du gestionnaire responsive."""
    global _responsive_manager
    if _responsive_manager is None:
        _responsive_manager = ResponsiveManager()
    return _responsive_manager
