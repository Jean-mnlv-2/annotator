#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests unitaires pour le gestionnaire de thèmes.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

# Mock PyQt pour les tests
import sys
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()

from libs.theme_manager import (
    ThemeManager, ColorScheme, ModernTheme, ThemeMode
)


class TestColorScheme(unittest.TestCase):
    """Tests pour ColorScheme."""
    
    def setUp(self):
        """Configuration des tests."""
        self.colors = {
            'primary': '#2563eb',
            'background': '#ffffff',
            'text': '#000000'
        }
        self.scheme = ColorScheme("Test", self.colors)
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.scheme.name, "Test")
        self.assertEqual(self.scheme.colors, self.colors)
    
    def test_get_color(self):
        """Test de récupération de couleur."""
        color = self.scheme.get_color('primary')
        self.assertIsNotNone(color)
        
        # Vérifier que la couleur est mise en cache
        self.assertIn('primary', self.scheme._color_cache)
    
    def test_get_color_invalid(self):
        """Test de récupération de couleur inexistante."""
        color = self.scheme.get_color('invalid')
        self.assertEqual(color.name(), "#000000")  # Couleur par défaut
    
    def test_to_dict(self):
        """Test de conversion en dictionnaire."""
        result = self.scheme.to_dict()
        self.assertEqual(result, self.colors)


class TestModernTheme(unittest.TestCase):
    """Tests pour ModernTheme."""
    
    def setUp(self):
        """Configuration des tests."""
        self.light_colors = {
            'background': '#ffffff',
            'text': '#000000'
        }
        self.dark_colors = {
            'background': '#000000',
            'text': '#ffffff'
        }
        
        self.light_scheme = ColorScheme("Light", self.light_colors)
        self.dark_scheme = ColorScheme("Dark", self.dark_colors)
        self.theme = ModernTheme("Test", self.light_scheme, self.dark_scheme)
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.theme.name, "Test")
        self.assertEqual(self.theme.light_scheme, self.light_scheme)
        self.assertEqual(self.theme.dark_scheme, self.dark_scheme)
        self.assertEqual(self.theme.font_family, "Segoe UI")
        self.assertEqual(self.theme.font_size, 9)
    
    def test_get_scheme_light(self):
        """Test de récupération du schéma clair."""
        scheme = self.theme.get_scheme(ThemeMode.LIGHT)
        self.assertEqual(scheme, self.light_scheme)
    
    def test_get_scheme_dark(self):
        """Test de récupération du schéma sombre."""
        scheme = self.theme.get_scheme(ThemeMode.DARK)
        self.assertEqual(scheme, self.dark_scheme)
    
    def test_get_scheme_auto(self):
        """Test de récupération du schéma auto."""
        scheme = self.theme.get_scheme(ThemeMode.AUTO)
        self.assertEqual(scheme, self.light_scheme)  # Par défaut light


class TestThemeManager(unittest.TestCase):
    """Tests pour ThemeManager."""
    
    def setUp(self):
        """Configuration des tests."""
        with patch('libs.theme_manager.QSettings'), \
             patch('libs.theme_manager.QApplication') as mock_app:
            self.theme_manager = ThemeManager()
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertIsNotNone(self.theme_manager.current_theme)
        self.assertEqual(self.theme_manager.current_mode, ThemeMode.LIGHT)
        self.assertIn("modern", self.theme_manager.themes)
        self.assertIn("classic", self.theme_manager.themes)
    
    def test_set_theme_valid(self):
        """Test de changement de thème valide."""
        result = self.theme_manager.set_theme("modern")
        self.assertTrue(result)
        self.assertEqual(self.theme_manager.current_theme.name, "modern")
    
    def test_set_theme_invalid(self):
        """Test de changement de thème invalide."""
        result = self.theme_manager.set_theme("invalid_theme")
        self.assertFalse(result)
    
    def test_set_mode(self):
        """Test de changement de mode."""
        self.theme_manager.set_mode(ThemeMode.DARK)
        self.assertEqual(self.theme_manager.current_mode, ThemeMode.DARK)
    
    def test_get_available_themes(self):
        """Test de récupération des thèmes disponibles."""
        themes = self.theme_manager.get_available_themes()
        self.assertIn("modern", themes)
        self.assertIn("classic", themes)
    
    def test_get_current_scheme(self):
        """Test de récupération du schéma actuel."""
        scheme = self.theme_manager.get_current_scheme()
        self.assertIsNotNone(scheme)
    
    def test_create_custom_theme(self):
        """Test de création de thème personnalisé."""
        light_colors = {'background': '#ffffff'}
        dark_colors = {'background': '#000000'}
        
        result = self.theme_manager.create_custom_theme(
            "Custom", light_colors, dark_colors
        )
        self.assertTrue(result)
        self.assertIn("Custom", self.theme_manager.custom_themes)
    
    def test_create_custom_theme_invalid(self):
        """Test de création de thème personnalisé invalide."""
        result = self.theme_manager.create_custom_theme(
            "", {}, {}  # Nom vide
        )
        self.assertFalse(result)
    
    def test_delete_custom_theme(self):
        """Test de suppression de thème personnalisé."""
        # Créer d'abord un thème
        light_colors = {'background': '#ffffff'}
        dark_colors = {'background': '#000000'}
        self.theme_manager.create_custom_theme("Custom", light_colors, dark_colors)
        
        # Le supprimer
        result = self.theme_manager.delete_custom_theme("Custom")
        self.assertTrue(result)
        self.assertNotIn("Custom", self.theme_manager.custom_themes)
    
    def test_delete_custom_theme_invalid(self):
        """Test de suppression de thème personnalisé inexistant."""
        result = self.theme_manager.delete_custom_theme("Invalid")
        self.assertFalse(result)
    
    def test_set_animations_enabled(self):
        """Test d'activation/désactivation des animations."""
        self.theme_manager.set_animations_enabled(False)
        self.assertFalse(self.theme_manager.animations_enabled)
        
        self.theme_manager.set_animations_enabled(True)
        self.assertTrue(self.theme_manager.animations_enabled)
    
    def test_get_theme_info(self):
        """Test de récupération des informations du thème."""
        info = self.theme_manager.get_theme_info()
        
        self.assertIn('current_theme', info)
        self.assertIn('current_mode', info)
        self.assertIn('animations_enabled', info)
        self.assertIn('auto_switch_enabled', info)
        self.assertIn('available_themes', info)
    
    @patch('libs.theme_manager.QApplication')
    def test_apply_theme(self, mock_app):
        """Test d'application du thème."""
        mock_app.instance.return_value = Mock()
        
        # Cette méthode est privée mais on peut tester son effet
        self.theme_manager.set_theme("modern")
        # Vérifier que le thème a été changé
        self.assertEqual(self.theme_manager.current_theme.name, "modern")


class TestThemeManagerIntegration(unittest.TestCase):
    """Tests d'intégration pour ThemeManager."""
    
    def setUp(self):
        """Configuration des tests."""
        with patch('libs.theme_manager.QSettings'), \
             patch('libs.theme_manager.QApplication'):
            self.theme_manager = ThemeManager()
    
    def test_theme_switching_workflow(self):
        """Test du workflow de changement de thème."""
        # Commencer avec le thème moderne en mode clair
        self.theme_manager.set_theme("modern")
        self.theme_manager.set_mode(ThemeMode.LIGHT)
        
        scheme = self.theme_manager.get_current_scheme()
        self.assertEqual(scheme.name, "Light")
        
        # Passer en mode sombre
        self.theme_manager.set_mode(ThemeMode.DARK)
        scheme = self.theme_manager.get_current_scheme()
        self.assertEqual(scheme.name, "Dark")
        
        # Changer de thème
        self.theme_manager.set_theme("classic")
        scheme = self.theme_manager.get_current_scheme()
        self.assertEqual(scheme.name, "Classic Light")
    
    def test_custom_theme_workflow(self):
        """Test du workflow de thème personnalisé."""
        # Créer un thème personnalisé
        light_colors = {
            'background': '#f0f0f0',
            'text': '#333333'
        }
        dark_colors = {
            'background': '#1a1a1a',
            'text': '#cccccc'
        }
        
        result = self.theme_manager.create_custom_theme(
            "MyTheme", light_colors, dark_colors
        )
        self.assertTrue(result)
        
        # Utiliser le thème personnalisé
        result = self.theme_manager.set_theme("MyTheme")
        self.assertTrue(result)
        self.assertEqual(self.theme_manager.current_theme.name, "MyTheme")
        
        # Vérifier que les couleurs sont correctes
        scheme = self.theme_manager.get_current_scheme()
        self.assertEqual(scheme.get_color('background').name(), "#f0f0f0")
        
        # Supprimer le thème
        result = self.theme_manager.delete_custom_theme("MyTheme")
        self.assertTrue(result)
    
    def test_theme_persistence(self):
        """Test de persistance des thèmes."""
        # Simuler le chargement des settings
        mock_settings_data = {
            'theme/name': 'modern',
            'theme/mode': 'dark',
            'theme/animations': True
        }
        
        with patch.object(self.theme_manager.settings, 'value') as mock_value:
            def side_effect(key, default=None):
                return mock_settings_data.get(key, default)
            
            mock_value.side_effect = side_effect
            
            # Recréer le gestionnaire pour tester le chargement
            with patch('libs.theme_manager.QSettings'), \
                 patch('libs.theme_manager.QApplication'):
                new_manager = ThemeManager()
                new_manager._load_settings()
                
                # Vérifier que les settings ont été chargés
                self.assertEqual(new_manager.current_theme.name, "modern")
                self.assertEqual(new_manager.current_mode, ThemeMode.DARK)
    
    def test_theme_validation(self):
        """Test de validation des thèmes."""
        # Test avec des couleurs valides
        valid_light = {'background': '#ffffff', 'text': '#000000'}
        valid_dark = {'background': '#000000', 'text': '#ffffff'}
        
        result = self.theme_manager.create_custom_theme(
            "ValidTheme", valid_light, valid_dark
        )
        self.assertTrue(result)
        
        # Test avec des couleurs invalides
        invalid_colors = {'invalid_key': 'invalid_value'}
        
        result = self.theme_manager.create_custom_theme(
            "InvalidTheme", invalid_colors, invalid_colors
        )
        # Devrait quand même fonctionner mais avec des valeurs par défaut
        self.assertTrue(result)


class TestThemeMode(unittest.TestCase):
    """Tests pour ThemeMode."""
    
    def test_enum_values(self):
        """Test des valeurs de l'enum."""
        self.assertEqual(ThemeMode.LIGHT.value, "light")
        self.assertEqual(ThemeMode.DARK.value, "dark")
        self.assertEqual(ThemeMode.AUTO.value, "auto")
        self.assertEqual(ThemeMode.CUSTOM.value, "custom")
    
    def test_enum_creation(self):
        """Test de création d'enum."""
        mode = ThemeMode("light")
        self.assertEqual(mode, ThemeMode.LIGHT)
        
        mode = ThemeMode("dark")
        self.assertEqual(mode, ThemeMode.DARK)


if __name__ == '__main__':
    unittest.main()
