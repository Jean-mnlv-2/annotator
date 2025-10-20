#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from typing import Dict, Any, Optional, List
from enum import Enum

try:
    from PyQt5.QtGui import QPalette, QColor, QFont, QIcon, QPixmap, QPainter
    from PyQt5.QtCore import QObject, pyqtSignal, QSettings, QTimer
    from PyQt5.QtWidgets import QApplication, QWidget, QStyleFactory
except ImportError:
    from PyQt4.QtGui import QPalette, QColor, QFont, QIcon, QPixmap, QPainter, QApplication
    from PyQt4.QtCore import QObject, pyqtSignal, QSettings, QTimer
    from PyQt4.QtWidgets import QWidget, QStyleFactory


class ThemeMode(Enum):
    """Modes de thème disponibles."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    CUSTOM = "custom"


class ColorScheme:
    """Schéma de couleurs pour un thème."""
    
    def __init__(self, name: str, colors: Dict[str, str]):
        self.name = name
        self.colors = colors
        self._color_cache = {}
    
    def get_color(self, key: str) -> QColor:
        """Retourne une couleur QColor."""
        if key in self._color_cache:
            return self._color_cache[key]
        
        color_str = self.colors.get(key, "#000000")
        color = QColor(color_str)
        self._color_cache[key] = color
        return color
    
    def to_dict(self) -> Dict[str, str]:
        """Convertit le schéma en dictionnaire."""
        return self.colors.copy()


class ModernTheme:
    """Thème moderne avec support du mode sombre."""
    
    def __init__(self, name: str, light_scheme: ColorScheme, dark_scheme: ColorScheme):
        self.name = name
        self.light_scheme = light_scheme
        self.dark_scheme = dark_scheme
        self.font_family = "Segoe UI"  # Police moderne
        self.font_size = 9
        self.border_radius = 6
        self.animation_duration = 200
    
    def get_scheme(self, mode: ThemeMode) -> ColorScheme:
        """Retourne le schéma de couleurs selon le mode."""
        if mode == ThemeMode.DARK:
            return self.dark_scheme
        else:
            return self.light_scheme


class ThemeManager(QObject):
    """
    Gestionnaire de thèmes avec support du mode sombre et animations.
    """
    
    # Signaux
    themeChanged = pyqtSignal(str, str)  # theme_name, mode
    colorSchemeChanged = pyqtSignal(ColorScheme)
    animationStateChanged = pyqtSignal(bool)  # enabled/disabled
    
    def __init__(self):
        super().__init__()
        
        self.current_theme = None
        self.current_mode = ThemeMode.LIGHT
        self.themes = {}
        self.custom_themes = {}
        
        # Configuration
        self.animations_enabled = True
        self.auto_switch_enabled = True
        
        # Timer pour le mode auto (basé sur l'heure)
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self._check_auto_mode)
        self.auto_timer.start(60000)  # Vérifier chaque minute
        
        # Settings pour persistance
        self.settings = QSettings("AKOUMA", "Annotator")
        
        # Initialiser les thèmes par défaut
        self._initialize_default_themes()
        
        # Charger la configuration sauvegardée
        self._load_settings()
        
        # Appliquer le thème initial
        self._apply_theme()
    
    def _initialize_default_themes(self):
        """Initialise les thèmes par défaut."""
        
        # Thème Light moderne
        light_colors = {
            # Couleurs principales
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'primary_pressed': '#1e40af',
            'secondary': '#64748b',
            'accent': '#0ea5e9',
            
            # Couleurs de fond
            'background': '#ffffff',
            'background_secondary': '#f8fafc',
            'background_tertiary': '#f1f5f9',
            'surface': '#ffffff',
            'surface_hover': '#f1f5f9',
            'surface_pressed': '#e2e8f0',
            
            # Couleurs de texte
            'text_primary': '#0f172a',
            'text_secondary': '#475569',
            'text_tertiary': '#94a3b8',
            'text_disabled': '#cbd5e1',
            'text_inverse': '#ffffff',
            
            # Couleurs de bordure
            'border': '#e2e8f0',
            'border_hover': '#cbd5e1',
            'border_focus': '#2563eb',
            'border_error': '#ef4444',
            
            # Couleurs d'état
            'success': '#22c55e',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'info': '#3b82f6',
            
            # Couleurs spéciales pour l'annotation
            'annotation_default': '#3b82f6',
            'annotation_selected': '#ef4444',
            'annotation_hover': '#22c55e',
            'annotation_background': '#f8fafc',
            
            # Couleurs de canvas
            'canvas_background': '#ffffff',
            'canvas_grid': '#e2e8f0',
            'canvas_overlay': '#00000020',
            
            # Couleurs de toolbar
            'toolbar_background': '#ffffff',
            'toolbar_border': '#e2e8f0',
            'toolbar_button': '#f8fafc',
            'toolbar_button_hover': '#f1f5f9',
            'toolbar_button_pressed': '#e2e8f0',
            
            # Couleurs de menu
            'menu_background': '#ffffff',
            'menu_border': '#e2e8f0',
            'menu_item': '#f8fafc',
            'menu_item_hover': '#f1f5f9',
            'menu_item_selected': '#dbeafe',
            
            # Couleurs de dialog
            'dialog_background': '#ffffff',
            'dialog_border': '#e2e8f0',
            'dialog_shadow': '#00000040',
        }
        
        light_scheme = ColorScheme("Light", light_colors)
        
        # Thème Dark moderne
        dark_colors = {
            # Couleurs principales
            'primary': '#3b82f6',
            'primary_hover': '#2563eb',
            'primary_pressed': '#1d4ed8',
            'secondary': '#64748b',
            'accent': '#0ea5e9',
            
            # Couleurs de fond
            'background': '#0f172a',
            'background_secondary': '#1e293b',
            'background_tertiary': '#334155',
            'surface': '#1e293b',
            'surface_hover': '#334155',
            'surface_pressed': '#475569',
            
            # Couleurs de texte
            'text_primary': '#f8fafc',
            'text_secondary': '#cbd5e1',
            'text_tertiary': '#94a3b8',
            'text_disabled': '#64748b',
            'text_inverse': '#0f172a',
            
            # Couleurs de bordure
            'border': '#334155',
            'border_hover': '#475569',
            'border_focus': '#3b82f6',
            'border_error': '#ef4444',
            
            # Couleurs d'état
            'success': '#22c55e',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'info': '#3b82f6',
            
            # Couleurs spéciales pour l'annotation
            'annotation_default': '#60a5fa',
            'annotation_selected': '#f87171',
            'annotation_hover': '#34d399',
            'annotation_background': '#1e293b',
            
            # Couleurs de canvas
            'canvas_background': '#0f172a',
            'canvas_grid': '#334155',
            'canvas_overlay': '#ffffff20',
            
            # Couleurs de toolbar
            'toolbar_background': '#1e293b',
            'toolbar_border': '#334155',
            'toolbar_button': '#334155',
            'toolbar_button_hover': '#475569',
            'toolbar_button_pressed': '#64748b',
            
            # Couleurs de menu
            'menu_background': '#1e293b',
            'menu_border': '#334155',
            'menu_item': '#334155',
            'menu_item_hover': '#475569',
            'menu_item_selected': '#1e40af',
            
            # Couleurs de dialog
            'dialog_background': '#1e293b',
            'dialog_border': '#334155',
            'dialog_shadow': '#00000060',
        }
        
        dark_scheme = ColorScheme("Dark", dark_colors)
        
        # Créer le thème moderne
        modern_theme = ModernTheme("Modern", light_scheme, dark_scheme)
        self.themes["modern"] = modern_theme
        
        # Thème classique (pour compatibilité)
        classic_light = ColorScheme("Classic Light", {
            'background': '#ffffff',
            'text_primary': '#000000',
            'primary': '#0078d4',
            'border': '#d1d1d1',
        })
        
        classic_dark = ColorScheme("Classic Dark", {
            'background': '#2d2d30',
            'text_primary': '#ffffff',
            'primary': '#0078d4',
            'border': '#464647',
        })
        
        classic_theme = ModernTheme("Classic", classic_light, classic_dark)
        self.themes["classic"] = classic_theme
    
    def _load_settings(self):
        """Charge la configuration depuis les settings."""
        theme_name = self.settings.value("theme/name", "modern", str)
        mode_str = self.settings.value("theme/mode", "light", str)
        self.animations_enabled = self.settings.value("theme/animations", True, bool)
        
        try:
            self.current_mode = ThemeMode(mode_str)
        except ValueError:
            self.current_mode = ThemeMode.LIGHT
        
        if theme_name in self.themes:
            self.current_theme = self.themes[theme_name]
        else:
            self.current_theme = self.themes["modern"]
        
        # Charger les thèmes personnalisés
        custom_themes_data = self.settings.value("theme/custom", {})
        for name, data in custom_themes_data.items():
            try:
                light_scheme = ColorScheme(f"{name} Light", data['light'])
                dark_scheme = ColorScheme(f"{name} Dark", data['dark'])
                custom_theme = ModernTheme(name, light_scheme, dark_scheme)
                self.custom_themes[name] = custom_theme
            except Exception as e:
                print(f"Erreur lors du chargement du thème personnalisé {name}: {e}")
    
    def _save_settings(self):
        """Sauvegarde la configuration."""
        self.settings.setValue("theme/name", self.current_theme.name)
        self.settings.setValue("theme/mode", self.current_mode.value)
        self.settings.setValue("theme/animations", self.animations_enabled)
        
        # Sauvegarder les thèmes personnalisés
        custom_data = {}
        for name, theme in self.custom_themes.items():
            custom_data[name] = {
                'light': theme.light_scheme.to_dict(),
                'dark': theme.dark_scheme.to_dict()
            }
        self.settings.setValue("theme/custom", custom_data)
    
    def _apply_theme(self):
        """Applique le thème actuel."""
        if not self.current_theme:
            return
        
        app = QApplication.instance()
        if not app:
            return
        
        # Obtenir le schéma de couleurs actuel
        scheme = self.current_theme.get_scheme(self.current_mode)
        
        # Appliquer la palette
        palette = self._create_palette(scheme)
        app.setPalette(palette)
        
        # Appliquer le style CSS
        stylesheet = self._create_stylesheet(scheme)
        app.setStyleSheet(stylesheet)
        
        # Émettre les signaux
        self.themeChanged.emit(self.current_theme.name, self.current_mode.value)
        self.colorSchemeChanged.emit(scheme)
        
        # Sauvegarder
        self._save_settings()
    
    def _create_palette(self, scheme: ColorScheme) -> QPalette:
        """Crée une palette Qt basée sur le schéma de couleurs."""
        palette = QPalette()
        
        # Couleurs de base
        palette.setColor(QPalette.Window, scheme.get_color('background'))
        palette.setColor(QPalette.WindowText, scheme.get_color('text_primary'))
        palette.setColor(QPalette.Base, scheme.get_color('surface'))
        palette.setColor(QPalette.AlternateBase, scheme.get_color('background_secondary'))
        palette.setColor(QPalette.ToolTipBase, scheme.get_color('surface'))
        palette.setColor(QPalette.ToolTipText, scheme.get_color('text_primary'))
        palette.setColor(QPalette.Text, scheme.get_color('text_primary'))
        palette.setColor(QPalette.Button, scheme.get_color('surface'))
        palette.setColor(QPalette.ButtonText, scheme.get_color('text_primary'))
        palette.setColor(QPalette.BrightText, scheme.get_color('error'))
        palette.setColor(QPalette.Link, scheme.get_color('primary'))
        palette.setColor(QPalette.Highlight, scheme.get_color('primary'))
        palette.setColor(QPalette.HighlightedText, scheme.get_color('text_inverse'))
        
        return palette
    
    def _create_stylesheet(self, scheme: ColorScheme) -> str:
        """Crée un stylesheet CSS basé sur le schéma de couleurs."""
        primary = scheme.get_color('primary').name()
        primary_hover = scheme.get_color('primary_hover').name()
        primary_pressed = scheme.get_color('primary_pressed').name()
        background = scheme.get_color('background').name()
        background_secondary = scheme.get_color('background_secondary').name()
        surface = scheme.get_color('surface').name()
        surface_hover = scheme.get_color('surface_hover').name()
        surface_pressed = scheme.get_color('surface_pressed').name()
        text_primary = scheme.get_color('text_primary').name()
        text_secondary = scheme.get_color('text_secondary').name()
        border = scheme.get_color('border').name()
        border_hover = scheme.get_color('border_hover').name()
        border_focus = scheme.get_color('border_focus').name()
        success = scheme.get_color('success').name()
        warning = scheme.get_color('warning').name()
        error = scheme.get_color('error').name()
        
        return f"""
        /* Styles généraux */
        QWidget {{
            font-family: '{self.current_theme.font_family}';
            font-size: {self.current_theme.font_size}pt;
            color: {text_primary};
            background-color: {background};
        }}
        
        /* Boutons */
        QPushButton {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            padding: 8px 16px;
            min-height: 20px;
        }}
        
        QPushButton:hover {{
            background-color: {surface_hover};
            border-color: {border_hover};
        }}
        
        QPushButton:pressed {{
            background-color: {surface_pressed};
        }}
        
        QPushButton:disabled {{
            background-color: {background_secondary};
            color: {text_secondary};
            border-color: {border};
        }}
        
        /* Boutons primaires */
        QPushButton[primary="true"] {{
            background-color: {primary};
            color: white;
            border-color: {primary};
        }}
        
        QPushButton[primary="true"]:hover {{
            background-color: {primary_hover};
            border-color: {primary_hover};
        }}
        
        QPushButton[primary="true"]:pressed {{
            background-color: {primary_pressed};
            border-color: {primary_pressed};
        }}
        
        /* Champs de texte */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            padding: 6px 8px;
            selection-background-color: {primary};
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {border_focus};
        }}
        
        /* Combobox */
        QComboBox {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            padding: 6px 8px;
            min-width: 80px;
        }}
        
        QComboBox:hover {{
            border-color: {border_hover};
        }}
        
        QComboBox:focus {{
            border-color: {border_focus};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {text_secondary};
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {surface};
            border: 1px solid {border};
            selection-background-color: {primary};
        }}
        
        /* Listes */
        QListWidget, QListView {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            selection-background-color: {primary};
            alternate-background-color: {background_secondary};
        }}
        
        QListWidget::item, QListView::item {{
            padding: 4px 8px;
            border-bottom: 1px solid {border};
        }}
        
        QListWidget::item:hover, QListView::item:hover {{
            background-color: {surface_hover};
        }}
        
        QListWidget::item:selected, QListView::item:selected {{
            background-color: {primary};
            color: white;
        }}
        
        /* Toolbar */
        QToolBar {{
            background-color: {surface};
            border: 1px solid {border};
            spacing: 2px;
        }}
        
        QToolButton {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: {self.current_theme.border_radius}px;
            padding: 4px;
            margin: 1px;
        }}
        
        QToolButton:hover {{
            background-color: {surface_hover};
            border-color: {border_hover};
        }}
        
        QToolButton:pressed {{
            background-color: {surface_pressed};
        }}
        
        QToolButton:checked {{
            background-color: {primary};
            color: white;
        }}
        
        /* Menu */
        QMenuBar {{
            background-color: {surface};
            border-bottom: 1px solid {border};
        }}
        
        QMenuBar::item {{
            background-color: transparent;
            padding: 4px 8px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {surface_hover};
        }}
        
        QMenu {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
        }}
        
        QMenu::item {{
            padding: 6px 16px;
        }}
        
        QMenu::item:selected {{
            background-color: {surface_hover};
        }}
        
        QMenu::separator {{
            height: 1px;
            background-color: {border};
            margin: 2px 0px;
        }}
        
        /* Dock widgets */
        QDockWidget {{
            background-color: {surface};
            border: 1px solid {border};
        }}
        
        QDockWidget::title {{
            background-color: {background_secondary};
            border-bottom: 1px solid {border};
            padding: 4px 8px;
            font-weight: bold;
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            background-color: {background_secondary};
            width: 12px;
            border: none;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {border_hover};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {text_secondary};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        QScrollBar:horizontal {{
            background-color: {background_secondary};
            height: 12px;
            border: none;
        }}
        
        QScrollBar::handle:horizontal {{
            background-color: {border_hover};
            border-radius: 6px;
            min-width: 20px;
        }}
        
        QScrollBar::handle:horizontal:hover {{
            background-color: {text_secondary};
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            border: none;
            background: none;
        }}
        
        /* Status bar */
        QStatusBar {{
            background-color: {background_secondary};
            border-top: 1px solid {border};
        }}
        
        /* Progress bar */
        QProgressBar {{
            background-color: {background_secondary};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {primary};
            border-radius: {self.current_theme.border_radius - 1}px;
        }}
        
        /* Tab widget */
        QTabWidget::pane {{
            background-color: {surface};
            border: 1px solid {border};
        }}
        
        QTabBar::tab {{
            background-color: {background_secondary};
            border: 1px solid {border};
            padding: 6px 12px;
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {surface};
            border-bottom: none;
        }}
        
        QTabBar::tab:hover {{
            background-color: {surface_hover};
        }}
        
        /* Slider */
        QSlider::groove:horizontal {{
            background-color: {background_secondary};
            height: 6px;
            border-radius: 3px;
        }}
        
        QSlider::handle:horizontal {{
            background-color: {primary};
            width: 16px;
            height: 16px;
            border-radius: 8px;
            margin: -5px 0;
        }}
        
        QSlider::handle:horizontal:hover {{
            background-color: {primary_hover};
        }}
        
        /* Checkbox et Radio */
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {border};
            border-radius: 2px;
            background-color: {surface};
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {primary};
            image: none;
        }}
        
        QCheckBox::indicator:checked::after {{
            content: "✓";
            color: white;
            font-weight: bold;
        }}
        
        QRadioButton::indicator {{
            border-radius: 8px;
        }}
        
        QRadioButton::indicator:checked {{
            background-color: {primary};
        }}
        
        /* Spinbox */
        QSpinBox, QDoubleSpinBox {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            padding: 4px 6px;
        }}
        
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {border_focus};
        }}
        
        /* Group box */
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {border};
            border-radius: {self.current_theme.border_radius}px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
        }}
        
        /* Messages d'état */
        .success {{
            color: {success};
        }}
        
        .warning {{
            color: {warning};
        }}
        
        .error {{
            color: {error};
        }}
        
        .info {{
            color: {primary};
        }}
        """
    
    def set_theme(self, theme_name: str):
        """Change le thème actuel."""
        if theme_name in self.themes:
            self.current_theme = self.themes[theme_name]
        elif theme_name in self.custom_themes:
            self.current_theme = self.custom_themes[theme_name]
        else:
            return False
        
        self._apply_theme()
        return True
    
    def set_mode(self, mode: ThemeMode):
        """Change le mode du thème."""
        if mode == ThemeMode.AUTO:
            self.auto_switch_enabled = True
            self._check_auto_mode()
        else:
            self.auto_switch_enabled = False
            self.current_mode = mode
            self._apply_theme()
    
    def _check_auto_mode(self):
        """Vérifie et applique le mode automatique basé sur l'heure."""
        if not self.auto_switch_enabled:
            return
        
        from datetime import datetime
        current_hour = datetime.now().hour
        
        # Mode sombre de 18h à 6h
        if 18 <= current_hour or current_hour < 6:
            new_mode = ThemeMode.DARK
        else:
            new_mode = ThemeMode.LIGHT
        
        if new_mode != self.current_mode:
            self.current_mode = new_mode
            self._apply_theme()
    
    def get_available_themes(self) -> List[str]:
        """Retourne la liste des thèmes disponibles."""
        themes = list(self.themes.keys())
        themes.extend(self.custom_themes.keys())
        return themes
    
    def get_current_scheme(self) -> ColorScheme:
        """Retourne le schéma de couleurs actuel."""
        if self.current_theme:
            return self.current_theme.get_scheme(self.current_mode)
        return None
    
    def create_custom_theme(self, name: str, light_colors: Dict[str, str], 
                           dark_colors: Dict[str, str]) -> bool:
        """Crée un thème personnalisé."""
        try:
            light_scheme = ColorScheme(f"{name} Light", light_colors)
            dark_scheme = ColorScheme(f"{name} Dark", dark_colors)
            custom_theme = ModernTheme(name, light_scheme, dark_scheme)
            
            self.custom_themes[name] = custom_theme
            self._save_settings()
            return True
        except Exception as e:
            print(f"Erreur lors de la création du thème {name}: {e}")
            return False
    
    def delete_custom_theme(self, name: str) -> bool:
        """Supprime un thème personnalisé."""
        if name in self.custom_themes:
            del self.custom_themes[name]
            self._save_settings()
            return True
        return False
    
    def set_animations_enabled(self, enabled: bool):
        """Active/désactive les animations."""
        self.animations_enabled = enabled
        self.animationStateChanged.emit(enabled)
        self._save_settings()
    
    def get_theme_info(self) -> Dict[str, Any]:
        """Retourne les informations du thème actuel."""
        return {
            'current_theme': self.current_theme.name if self.current_theme else None,
            'current_mode': self.current_mode.value,
            'animations_enabled': self.animations_enabled,
            'auto_switch_enabled': self.auto_switch_enabled,
            'available_themes': self.get_available_themes(),
            'font_family': self.current_theme.font_family if self.current_theme else None,
            'font_size': self.current_theme.font_size if self.current_theme else None
        }


# Instance globale du gestionnaire de thèmes
_theme_manager = None

def get_theme_manager() -> ThemeManager:
    """Retourne l'instance globale du gestionnaire de thèmes."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
