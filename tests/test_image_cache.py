#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests unitaires pour le gestionnaire de cache d'images.
"""

import unittest
import tempfile
import os
import time
from unittest.mock import Mock, patch, MagicMock

# Mock PyQt pour les tests
import sys
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()

from libs.image_cache import ImageCacheManager, ImageCacheItem, ImagePreloader


class TestImageCacheItem(unittest.TestCase):
    """Tests pour ImageCacheItem."""
    
    def setUp(self):
        """Configuration des tests."""
        self.test_path = "/tmp/test_image.jpg"
        self.test_image = Mock()
        self.test_pixmap = Mock()
        self.test_size = 1024
        self.test_time = time.time()
    
    def test_init(self):
        """Test de l'initialisation."""
        item = ImageCacheItem(
            self.test_path, self.test_image, self.test_pixmap,
            self.test_size, self.test_time
        )
        
        self.assertEqual(item.image_path, self.test_path)
        self.assertEqual(item.image, self.test_image)
        self.assertEqual(item.pixmap, self.test_pixmap)
        self.assertEqual(item.file_size, self.test_size)
        self.assertEqual(item.last_access, self.test_time)
        self.assertEqual(item.access_count, 1)
    
    def test_update_access(self):
        """Test de la mise à jour d'accès."""
        item = ImageCacheItem(
            self.test_path, self.test_image, self.test_pixmap,
            self.test_size, self.test_time
        )
        
        initial_count = item.access_count
        initial_time = item.last_access
        
        time.sleep(0.01)  # Petit délai pour s'assurer que le temps change
        item.update_access()
        
        self.assertEqual(item.access_count, initial_count + 1)
        self.assertGreater(item.last_access, initial_time)
    
    @patch('os.stat')
    def test_compute_hash(self, mock_stat):
        """Test du calcul du hash."""
        mock_stat.return_value = Mock(st_mtime=1234567890, st_size=1024)
        
        item = ImageCacheItem(
            self.test_path, self.test_image, self.test_pixmap,
            self.test_size, self.test_time
        )
        
        hash_value = item._compute_hash(self.test_path)
        
        self.assertIsInstance(hash_value, str)
        self.assertGreater(len(hash_value), 0)
        mock_stat.assert_called_once_with(self.test_path)


class TestImageCacheManager(unittest.TestCase):
    """Tests pour ImageCacheManager."""
    
    def setUp(self):
        """Configuration des tests."""
        self.cache_manager = ImageCacheManager(max_memory_mb=10, max_items=5)
        self.test_image = Mock()
        self.test_pixmap = Mock()
        self.test_image.isNull.return_value = False
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.cache_manager.max_memory_mb, 10)
        self.assertEqual(self.cache_manager.max_items, 5)
        self.assertEqual(self.cache_manager.current_memory_mb, 0)
        self.assertEqual(len(self.cache_manager.cache), 0)
    
    def test_get_image_not_in_cache(self):
        """Test de récupération d'image non en cache."""
        with patch('os.path.exists', return_value=True):
            result = self.cache_manager.get_image("/tmp/test.jpg")
            self.assertIsNone(result)
    
    def test_put_and_get_image(self):
        """Test d'ajout et récupération d'image."""
        test_path = "/tmp/test.jpg"
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            # Ajouter l'image
            self.cache_manager.put_image(test_path, self.test_image, self.test_pixmap)
            
            # Vérifier qu'elle est en cache
            self.assertTrue(self.cache_manager.is_cached(test_path))
            
            # Récupérer l'image
            result = self.cache_manager.get_image(test_path)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], self.test_image)
            self.assertEqual(result[1], self.test_pixmap)
    
    def test_cache_limit_items(self):
        """Test de la limite d'éléments en cache."""
        # Ajouter plus d'éléments que la limite
        for i in range(7):  # Limite est 5
            test_path = f"/tmp/test_{i}.jpg"
            with patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=1024):
                self.cache_manager.put_image(test_path, self.test_image, self.test_pixmap)
        
        # Vérifier que le cache ne dépasse pas la limite
        self.assertLessEqual(len(self.cache_manager.cache), 5)
    
    def test_cache_limit_memory(self):
        """Test de la limite de mémoire en cache."""
        # Ajouter des images avec une taille importante
        large_size = 5 * 1024 * 1024  # 5MB par image
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=large_size):
            
            # Ajouter 3 images de 5MB chacune (total 15MB, limite 10MB)
            for i in range(3):
                test_path = f"/tmp/large_{i}.jpg"
                self.cache_manager.put_image(test_path, self.test_image, self.test_pixmap)
        
        # Vérifier que le cache ne dépasse pas la limite mémoire
        self.assertLessEqual(self.cache_manager.current_memory_mb, 10)
    
    def test_clear_cache(self):
        """Test du vidage du cache."""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            self.cache_manager.put_image("/tmp/test.jpg", self.test_image, self.test_pixmap)
            self.assertEqual(len(self.cache_manager.cache), 1)
            
            self.cache_manager.clear_cache()
            self.assertEqual(len(self.cache_manager.cache), 0)
            self.assertEqual(self.cache_manager.current_memory_mb, 0)
    
    def test_get_cache_stats(self):
        """Test des statistiques du cache."""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            self.cache_manager.put_image("/tmp/test.jpg", self.test_image, self.test_pixmap)
            
            stats = self.cache_manager.get_cache_stats()
            
            self.assertIn('items_count', stats)
            self.assertIn('memory_mb', stats)
            self.assertIn('hit_rate', stats)
            self.assertEqual(stats['items_count'], 1)
    
    def test_set_memory_limit(self):
        """Test de modification de la limite de mémoire."""
        self.cache_manager.set_memory_limit(20)
        self.assertEqual(self.cache_manager.max_memory_mb, 20)
    
    def test_set_max_items(self):
        """Test de modification du nombre max d'éléments."""
        self.cache_manager.set_max_items(10)
        self.assertEqual(self.cache_manager.max_items, 10)


class TestImagePreloader(unittest.TestCase):
    """Tests pour ImagePreloader."""
    
    def setUp(self):
        """Configuration des tests."""
        self.cache_manager = Mock()
        self.image_paths = ["/tmp/test1.jpg", "/tmp/test2.jpg", "/tmp/test3.jpg"]
        self.preloader = ImagePreloader(self.image_paths, self.cache_manager)
    
    def test_init(self):
        """Test de l'initialisation."""
        self.assertEqual(self.preloader.image_paths, self.image_paths)
        self.assertEqual(self.preloader.cache_manager, self.cache_manager)
        self.assertFalse(self.preloader.should_stop)
    
    def test_stop(self):
        """Test de l'arrêt du préchargeur."""
        self.preloader.stop()
        self.assertTrue(self.preloader.should_stop)
    
    @patch('libs.image_cache.QImageReader')
    @patch('libs.image_cache.QPixmap')
    def test_run_success(self, mock_pixmap, mock_reader_class):
        """Test d'exécution réussie."""
        # Mock des objets Qt
        mock_reader = Mock()
        mock_reader_class.return_value = mock_reader
        mock_reader.read.return_value = Mock(isNull=Mock(return_value=False))
        mock_pixmap.fromImage.return_value = Mock()
        
        # Mock des méthodes du cache manager
        self.cache_manager.is_cached.return_value = False
        
        # Exécuter le préchargeur
        self.preloader.run()
        
        # Vérifier que les images ont été traitées
        self.assertEqual(mock_reader_class.call_count, 3)
        mock_reader.setAutoTransform.assert_called_with(True)


class TestImageCacheIntegration(unittest.TestCase):
    """Tests d'intégration pour le système de cache."""
    
    def setUp(self):
        """Configuration des tests."""
        self.cache_manager = ImageCacheManager(max_memory_mb=10, max_items=3)
        self.test_image = Mock()
        self.test_pixmap = Mock()
        self.test_image.isNull.return_value = False
    
    def test_full_workflow(self):
        """Test du workflow complet."""
        test_paths = ["/tmp/test1.jpg", "/tmp/test2.jpg", "/tmp/test3.jpg", "/tmp/test4.jpg"]
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            # Ajouter toutes les images
            for path in test_paths:
                self.cache_manager.put_image(path, self.test_image, self.test_pixmap)
            
            # Vérifier que les 3 premières sont en cache (limite de 3)
            for i in range(3):
                self.assertTrue(self.cache_manager.is_cached(test_paths[i]))
            
            # La 4ème ne devrait pas être en cache (LRU)
            self.assertFalse(self.cache_manager.is_cached(test_paths[3]))
            
            # Accéder à la première image pour la remettre en tête
            result = self.cache_manager.get_image(test_paths[0])
            self.assertIsNotNone(result)
            
            # Ajouter une nouvelle image
            new_path = "/tmp/test5.jpg"
            self.cache_manager.put_image(new_path, self.test_image, self.test_pixmap)
            
            # La première image devrait toujours être en cache (récemment accédée)
            self.assertTrue(self.cache_manager.is_cached(test_paths[0]))
    
    def test_preload_workflow(self):
        """Test du workflow de préchargement."""
        test_paths = ["/tmp/test1.jpg", "/tmp/test2.jpg", "/tmp/test3.jpg"]
        priority_paths = ["/tmp/test2.jpg"]  # Priorité sur test2.jpg
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            # Démarrer le préchargement
            self.cache_manager.preload_images(test_paths, priority_paths)
            
            # Vérifier que le préchargeur a été créé
            self.assertIsNotNone(self.cache_manager.preloader)
    
    def test_memory_cleanup(self):
        """Test du nettoyage de mémoire."""
        # Ajouter des images jusqu'à dépasser la limite
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=3 * 1024 * 1024):  # 3MB par image
            
            # Ajouter 5 images de 3MB (total 15MB, limite 10MB)
            for i in range(5):
                test_path = f"/tmp/large_{i}.jpg"
                self.cache_manager.put_image(test_path, self.test_image, self.test_pixmap)
            
            # Vérifier que la mémoire est sous contrôle
            self.assertLessEqual(self.cache_manager.current_memory_mb, 10)
            
            # Vérifier que le cache contient moins d'éléments
            self.assertLess(len(self.cache_manager.cache), 5)


if __name__ == '__main__':
    unittest.main()
