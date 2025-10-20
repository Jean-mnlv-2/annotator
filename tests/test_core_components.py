#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests unitaires pour les composants core.
"""

import unittest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Mock PyQt pour les tests
import sys
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()

from core.project_manager import ProjectManager, ProjectInfo
from core.annotation_manager import AnnotationManager, Annotation, ImageAnnotation, AnnotationType
from core.config_manager import ConfigManager


class TestProjectInfo(unittest.TestCase):
    """Tests pour ProjectInfo."""
    
    def setUp(self):
        """Configuration des tests."""
        self.project_info = ProjectInfo("Test Project", "/tmp/test")
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.project_info.name, "Test Project")
        self.assertEqual(self.project_info.path, "/tmp/test")
        self.assertIsNotNone(self.project_info.created)
        self.assertEqual(self.project_info.modified, self.project_info.created)
        self.assertEqual(self.project_info.description, "")
        self.assertEqual(self.project_info.version, "1.0")
        self.assertEqual(self.project_info.author, "")
        self.assertEqual(self.project_info.tags, [])
        self.assertEqual(self.project_info.image_count, 0)
        self.assertEqual(self.project_info.annotation_count, 0)
        self.assertEqual(self.project_info.metadata, {})
    
    def test_to_dict(self):
        """Test de conversion en dictionnaire."""
        result = self.project_info.to_dict()
        
        self.assertIn('name', result)
        self.assertIn('path', result)
        self.assertIn('created', result)
        self.assertEqual(result['name'], "Test Project")
        self.assertEqual(result['path'], "/tmp/test")
    
    def test_from_dict(self):
        """Test de création depuis un dictionnaire."""
        data = {
            'name': 'Test Project 2',
            'path': '/tmp/test2',
            'description': 'Test description',
            'version': '2.0',
            'author': 'Test Author',
            'tags': ['test', 'project'],
            'image_count': 10,
            'annotation_count': 5
        }
        
        project_info = ProjectInfo.from_dict(data)
        
        self.assertEqual(project_info.name, 'Test Project 2')
        self.assertEqual(project_info.path, '/tmp/test2')
        self.assertEqual(project_info.description, 'Test description')
        self.assertEqual(project_info.version, '2.0')
        self.assertEqual(project_info.author, 'Test Author')
        self.assertEqual(project_info.tags, ['test', 'project'])
        self.assertEqual(project_info.image_count, 10)
        self.assertEqual(project_info.annotation_count, 5)


class TestProjectManager(unittest.TestCase):
    """Tests pour ProjectManager."""
    
    def setUp(self):
        """Configuration des tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_manager = ProjectManager()
    
    def tearDown(self):
        """Nettoyage après les tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertIsNone(self.project_manager.current_project)
        self.assertIsNone(self.project_manager.project_path)
        self.assertIsNone(self.project_manager.image_directory)
        self.assertIsNone(self.project_manager.annotation_directory)
        self.assertEqual(self.project_manager.image_files, [])
        self.assertEqual(self.project_manager.annotation_files, [])
        self.assertFalse(self.project_manager.is_project_open)
        self.assertFalse(self.project_manager.is_dirty)
    
    def test_create_project(self):
        """Test de création de projet."""
        project_path = os.path.join(self.temp_dir, "test_project")
        image_dir = os.path.join(self.temp_dir, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        result = self.project_manager.create_project(
            project_path, "Test Project", image_dir, 
            description="Test description"
        )
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(project_path))
        self.assertTrue(os.path.exists(os.path.join(project_path, "project.json")))
        self.assertTrue(os.path.exists(os.path.join(project_path, "settings.json")))
        self.assertTrue(os.path.exists(os.path.join(project_path, "annotations")))
        self.assertTrue(os.path.exists(os.path.join(project_path, "backups")))
        self.assertTrue(os.path.exists(os.path.join(project_path, "exports")))
    
    def test_open_project(self):
        """Test d'ouverture de projet."""
        # Créer d'abord un projet
        project_path = os.path.join(self.temp_dir, "test_project")
        image_dir = os.path.join(self.temp_dir, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        self.project_manager.create_project(
            project_path, "Test Project", image_dir
        )
        
        # Fermer le projet créé
        self.project_manager.close_project()
        
        # Rouvrir le projet
        result = self.project_manager.open_project(project_path)
        
        self.assertTrue(result)
        self.assertTrue(self.project_manager.is_project_open)
        self.assertEqual(self.project_manager.project_path, project_path)
        self.assertIsNotNone(self.project_manager.current_project)
        self.assertEqual(self.project_manager.current_project.name, "Test Project")
    
    def test_close_project(self):
        """Test de fermeture de projet."""
        # Créer et ouvrir un projet
        project_path = os.path.join(self.temp_dir, "test_project")
        image_dir = os.path.join(self.temp_dir, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        self.project_manager.create_project(project_path, "Test Project", image_dir)
        
        # Fermer le projet
        self.project_manager.close_project()
        
        self.assertFalse(self.project_manager.is_project_open)
        self.assertIsNone(self.project_manager.project_path)
        self.assertIsNone(self.project_manager.current_project)
    
    def test_save_project(self):
        """Test de sauvegarde de projet."""
        # Créer et ouvrir un projet
        project_path = os.path.join(self.temp_dir, "test_project")
        image_dir = os.path.join(self.temp_dir, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        self.project_manager.create_project(project_path, "Test Project", image_dir)
        
        # Marquer comme modifié
        self.project_manager.mark_dirty()
        
        # Sauvegarder
        result = self.project_manager.save_project()
        
        self.assertTrue(result)
        self.assertFalse(self.project_manager.is_dirty)
    
    def test_get_stats(self):
        """Test de récupération des statistiques."""
        stats = self.project_manager.get_stats()
        
        self.assertIn('is_open', stats)
        self.assertIn('project_path', stats)
        self.assertIn('image_count', stats)
        self.assertIn('annotation_count', stats)
        self.assertIn('is_dirty', stats)
        self.assertIn('recent_projects_count', stats)


class TestAnnotation(unittest.TestCase):
    """Tests pour Annotation."""
    
    def setUp(self):
        """Configuration des tests."""
        self.annotation = Annotation(
            AnnotationType.BOUNDING_BOX,
            "test_label",
            [(10, 10), (100, 100)],
            confidence=0.9,
            difficult=True
        )
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.annotation.type, AnnotationType.BOUNDING_BOX)
        self.assertEqual(self.annotation.label, "test_label")
        self.assertEqual(self.annotation.coordinates, [(10, 10), (100, 100)])
        self.assertEqual(self.annotation.confidence, 0.9)
        self.assertTrue(self.annotation.difficult)
        self.assertIsNotNone(self.annotation.id)
        self.assertIsNotNone(self.annotation.created)
        self.assertEqual(self.annotation.modified, self.annotation.created)
        self.assertEqual(self.annotation.metadata, {})
    
    def test_to_dict(self):
        """Test de conversion en dictionnaire."""
        result = self.annotation.to_dict()
        
        self.assertIn('type', result)
        self.assertIn('label', result)
        self.assertIn('coordinates', result)
        self.assertIn('confidence', result)
        self.assertIn('difficult', result)
        self.assertIn('id', result)
        self.assertEqual(result['type'], 'bounding_box')
        self.assertEqual(result['label'], 'test_label')
    
    def test_from_dict(self):
        """Test de création depuis un dictionnaire."""
        data = {
            'id': 'test_id',
            'type': 'polygon',
            'label': 'test_label_2',
            'coordinates': [(0, 0), (50, 50), (100, 0)],
            'confidence': 0.8,
            'difficult': False,
            'created': '2023-01-01T00:00:00',
            'modified': '2023-01-01T00:00:00',
            'metadata': {'test': 'value'}
        }
        
        annotation = Annotation.from_dict(data)
        
        self.assertEqual(annotation.id, 'test_id')
        self.assertEqual(annotation.type, AnnotationType.POLYGON)
        self.assertEqual(annotation.label, 'test_label_2')
        self.assertEqual(annotation.coordinates, [(0, 0), (50, 50), (100, 0)])
        self.assertEqual(annotation.confidence, 0.8)
        self.assertFalse(annotation.difficult)
        self.assertEqual(annotation.created, '2023-01-01T00:00:00')
        self.assertEqual(annotation.modified, '2023-01-01T00:00:00')
        self.assertEqual(annotation.metadata, {'test': 'value'})


class TestImageAnnotation(unittest.TestCase):
    """Tests pour ImageAnnotation."""
    
    def setUp(self):
        """Configuration des tests."""
        self.image_path = "/tmp/test_image.jpg"
        self.image_annotation = ImageAnnotation(self.image_path)
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.image_annotation.image_path, self.image_path)
        self.assertEqual(self.image_annotation.annotations, [])
        self.assertFalse(self.image_annotation.is_verified)
        self.assertFalse(self.image_annotation.is_annotated)
        self.assertIsNotNone(self.image_annotation.created)
        self.assertEqual(self.image_annotation.modified, self.image_annotation.created)
        self.assertEqual(self.image_annotation.metadata, {})
    
    def test_add_annotation(self):
        """Test d'ajout d'annotation."""
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        
        self.image_annotation.add_annotation(annotation)
        
        self.assertEqual(len(self.image_annotation.annotations), 1)
        self.assertTrue(self.image_annotation.is_annotated)
        self.assertGreater(self.image_annotation.modified, self.image_annotation.created)
    
    def test_remove_annotation(self):
        """Test de suppression d'annotation."""
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        self.image_annotation.add_annotation(annotation)
        
        result = self.image_annotation.remove_annotation(annotation.id)
        
        self.assertTrue(result)
        self.assertEqual(len(self.image_annotation.annotations), 0)
        self.assertFalse(self.image_annotation.is_annotated)
        
        # Test avec ID invalide
        result = self.image_annotation.remove_annotation("invalid_id")
        self.assertFalse(result)
    
    def test_get_annotation(self):
        """Test de récupération d'annotation."""
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        self.image_annotation.add_annotation(annotation)
        
        result = self.image_annotation.get_annotation(annotation.id)
        self.assertEqual(result, annotation)
        
        # Test avec ID invalide
        result = self.image_annotation.get_annotation("invalid_id")
        self.assertIsNone(result)
    
    def test_update_annotation(self):
        """Test de mise à jour d'annotation."""
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        self.image_annotation.add_annotation(annotation)
        
        result = self.image_annotation.update_annotation(
            annotation.id, label="updated", confidence=0.5
        )
        
        self.assertTrue(result)
        self.assertEqual(annotation.label, "updated")
        self.assertEqual(annotation.confidence, 0.5)
        self.assertGreater(annotation.modified, annotation.created)
        
        # Test avec ID invalide
        result = self.image_annotation.update_annotation("invalid_id", label="test")
        self.assertFalse(result)


class TestAnnotationManager(unittest.TestCase):
    """Tests pour AnnotationManager."""
    
    def setUp(self):
        """Configuration des tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.annotation_manager = AnnotationManager()
        self.annotation_manager.set_annotation_directory(self.temp_dir)
    
    def tearDown(self):
        """Nettoyage après les tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertIsNone(self.annotation_manager.annotation_directory)
        self.assertIsNone(self.annotation_manager.current_image_path)
        self.assertIsNone(self.annotation_manager.current_annotations)
        self.assertEqual(self.annotation_manager.annotations_cache, {})
        self.assertFalse(self.annotation_manager.auto_save)
    
    def test_set_annotation_directory(self):
        """Test de définition du répertoire d'annotations."""
        self.annotation_manager.set_annotation_directory(self.temp_dir)
        self.assertEqual(self.annotation_manager.annotation_directory, self.temp_dir)
    
    def test_load_annotations(self):
        """Test de chargement d'annotations."""
        image_path = "/tmp/test_image.jpg"
        
        result = self.annotation_manager.load_annotations(image_path)
        
        self.assertTrue(result)
        self.assertEqual(self.annotation_manager.current_image_path, image_path)
        self.assertIsNotNone(self.annotation_manager.current_annotations)
        self.assertEqual(self.annotation_manager.current_annotations.image_path, image_path)
    
    def test_add_annotation(self):
        """Test d'ajout d'annotation."""
        image_path = "/tmp/test_image.jpg"
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        
        result = self.annotation_manager.add_annotation(annotation, image_path)
        
        self.assertTrue(result)
        self.assertEqual(self.annotation_manager.stats['total_annotations'], 1)
    
    def test_remove_annotation(self):
        """Test de suppression d'annotation."""
        image_path = "/tmp/test_image.jpg"
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        
        self.annotation_manager.add_annotation(annotation, image_path)
        result = self.annotation_manager.remove_annotation(annotation.id, image_path)
        
        self.assertTrue(result)
        self.assertEqual(self.annotation_manager.stats['total_annotations'], 0)
    
    def test_verify_image(self):
        """Test de vérification d'image."""
        image_path = "/tmp/test_image.jpg"
        
        result = self.annotation_manager.verify_image(image_path, True)
        
        self.assertTrue(result)
    
    def test_get_annotations(self):
        """Test de récupération d'annotations."""
        image_path = "/tmp/test_image.jpg"
        annotation = Annotation(AnnotationType.BOUNDING_BOX, "test", [(0, 0), (100, 100)])
        
        self.annotation_manager.add_annotation(annotation, image_path)
        annotations = self.annotation_manager.get_annotations(image_path)
        
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].label, "test")
    
    def test_get_stats(self):
        """Test de récupération des statistiques."""
        stats = self.annotation_manager.get_stats()
        
        self.assertIn('total_annotations', stats)
        self.assertIn('total_images', stats)
        self.assertIn('annotated_images', stats)
        self.assertIn('verified_images', stats)


class TestConfigManager(unittest.TestCase):
    """Tests pour ConfigManager."""
    
    def setUp(self):
        """Configuration des tests."""
        with patch('core.config_manager.QSettings'):
            self.config_manager = ConfigManager()
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertIsNotNone(self.config_manager.config)
        self.assertIsNotNone(self.config_manager.default_config)
        self.assertFalse(self.config_manager.is_loaded)
        self.assertFalse(self.config_manager.is_dirty)
    
    def test_get_value(self):
        """Test de récupération de valeur."""
        value = self.config_manager.get_value('theme.name')
        self.assertEqual(value, 'modern')
        
        # Test avec valeur par défaut
        value = self.config_manager.get_value('nonexistent.key', 'default')
        self.assertEqual(value, 'default')
    
    def test_set_value(self):
        """Test de définition de valeur."""
        self.config_manager.set_value('theme.mode', 'dark')
        
        value = self.config_manager.get_value('theme.mode')
        self.assertEqual(value, 'dark')
        self.assertTrue(self.config_manager.is_dirty)
    
    def test_get_config(self):
        """Test de récupération de configuration complète."""
        config = self.config_manager.get_config()
        
        self.assertIsInstance(config, dict)
        self.assertIn('theme', config)
        self.assertIn('application', config)
    
    def test_set_config(self):
        """Test de définition de configuration complète."""
        new_config = {'test': {'key': 'value'}}
        self.config_manager.set_config(new_config)
        
        config = self.config_manager.get_config()
        self.assertEqual(config, new_config)
        self.assertTrue(self.config_manager.is_dirty)
    
    def test_reset_to_defaults(self):
        """Test de réinitialisation aux valeurs par défaut."""
        # Modifier une valeur
        self.config_manager.set_value('theme.mode', 'dark')
        
        # Réinitialiser
        self.config_manager.reset_to_defaults('theme')
        
        value = self.config_manager.get_value('theme.mode')
        self.assertEqual(value, 'light')
    
    def test_has_key(self):
        """Test de vérification d'existence de clé."""
        self.assertTrue(self.config_manager.has_key('theme.name'))
        self.assertFalse(self.config_manager.has_key('nonexistent.key'))
    
    def test_remove_key(self):
        """Test de suppression de clé."""
        # Ajouter une clé
        self.config_manager.set_value('test.key', 'value')
        self.assertTrue(self.config_manager.has_key('test.key'))
        
        # La supprimer
        result = self.config_manager.remove_key('test.key')
        self.assertTrue(result)
        self.assertFalse(self.config_manager.has_key('test.key'))
        
        # Test avec clé inexistante
        result = self.config_manager.remove_key('nonexistent.key')
        self.assertFalse(result)
    
    def test_validate_config(self):
        """Test de validation de configuration."""
        # Configuration valide
        errors = self.config_manager.validate_config()
        self.assertEqual(len(errors), 0)
        
        # Configuration invalide
        self.config_manager.set_value('memory.warning_threshold_mb', 5000)  # Trop élevé
        errors = self.config_manager.validate_config()
        self.assertGreater(len(errors), 0)
    
    def test_get_config_info(self):
        """Test de récupération d'informations sur la configuration."""
        info = self.config_manager.get_config_info()
        
        self.assertIn('config_file_path', info)
        self.assertIn('is_loaded', info)
        self.assertIn('is_dirty', info)
        self.assertIn('sections', info)
        self.assertIn('total_keys', info)


if __name__ == '__main__':
    unittest.main()
