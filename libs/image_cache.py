#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import threading
from collections import OrderedDict
from typing import Optional, List, Dict, Tuple
import hashlib

try:
    from PyQt5.QtGui import QImage, QPixmap, QImageReader
    from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker
except ImportError:
    from PyQt4.QtGui import QImage, QPixmap, QImageReader
    from PyQt4.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker


class ImageCacheItem:
    """Représente un élément du cache d'images."""
    
    def __init__(self, image_path: str, image: QImage, pixmap: QPixmap, 
                 file_size: int, last_access: float):
        self.image_path = image_path
        self.image = image
        self.pixmap = pixmap
        self.file_size = file_size
        self.last_access = last_access
        self.access_count = 1
        self.file_hash = self._compute_hash(image_path)
    
    def _compute_hash(self, path: str) -> str:
        """Calcule le hash du fichier pour détecter les changements."""
        try:
            stat = os.stat(path)
            return hashlib.md5(f"{path}_{stat.st_mtime}_{stat.st_size}".encode()).hexdigest()
        except:
            return ""
    
    def update_access(self):
        """Met à jour les informations d'accès."""
        self.last_access = time.time()
        self.access_count += 1


class ImagePreloader(QThread):
    """Thread pour précharger les images en arrière-plan."""
    
    imageLoaded = pyqtSignal(str, QImage, QPixmap)
    loadingProgress = pyqtSignal(str, int)
    
    def __init__(self, image_paths: List[str], cache_manager):
        super().__init__()
        self.image_paths = image_paths
        self.cache_manager = cache_manager
        self.should_stop = False
        self.mutex = QMutex()
    
    def stop(self):
        """Arrête le préchargement."""
        with QMutexLocker(self.mutex):
            self.should_stop = True
    
    def run(self):
        """Précharge les images."""
        total = len(self.image_paths)
        for i, path in enumerate(self.image_paths):
            with QMutexLocker(self.mutex):
                if self.should_stop:
                    break
            
            try:
                # Vérifier si l'image est déjà en cache
                if self.cache_manager.is_cached(path):
                    continue
                
                # Charger l'image
                reader = QImageReader(path)
                reader.setAutoTransform(True)
                image = reader.read()
                
                if not image.isNull():
                    pixmap = QPixmap.fromImage(image)
                    self.imageLoaded.emit(path, image, pixmap)
                
                # Émettre le progrès
                progress = int((i + 1) / total * 100)
                self.loadingProgress.emit(os.path.basename(path), progress)
                
            except Exception as e:
                print(f"Erreur lors du préchargement de {path}: {e}")
                continue


class ImageCacheManager(QObject):
    """Gestionnaire de cache intelligent pour les images."""
    
    cacheUpdated = pyqtSignal()
    preloadProgress = pyqtSignal(str, int)
    
    def __init__(self, max_memory_mb: int = 500, max_items: int = 100):
        super().__init__()
        self.max_memory_mb = max_memory_mb
        self.max_items = max_items
        self.cache = OrderedDict()  # LRU cache
        self.mutex = QMutex()
        self.current_memory_mb = 0
        self.preloader = None
        self.preload_enabled = True
        
        # Statistiques
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'preloaded': 0
        }
    
    def get_image(self, image_path: str) -> Optional[Tuple[QImage, QPixmap]]:
        """
        Récupère une image du cache.
        Retourne un tuple (QImage, QPixmap) ou None si pas trouvé.
        """
        if not os.path.exists(image_path):
            return None
        
        with QMutexLocker(self.mutex):
            # Vérifier si l'image est en cache
            if image_path in self.cache:
                item = self.cache[image_path]
                
                # Vérifier si le fichier a changé
                current_hash = item._compute_hash(image_path)
                if current_hash == item.file_hash:
                    # Cache hit - déplacer en fin de liste (LRU)
                    self.cache.move_to_end(image_path)
                    item.update_access()
                    self.stats['hits'] += 1
                    return item.image, item.pixmap
                else:
                    # Fichier changé - supprimer du cache
                    self._remove_item(image_path)
            
            # Cache miss
            self.stats['misses'] += 1
            return None
    
    def put_image(self, image_path: str, image: QImage, pixmap: QPixmap):
        """Ajoute une image au cache."""
        if image.isNull() or not os.path.exists(image_path):
            return
        
        file_size = os.path.getsize(image_path)
        item = ImageCacheItem(
            image_path=image_path,
            image=image,
            pixmap=pixmap,
            file_size=file_size,
            last_access=time.time()
        )
        
        with QMutexLocker(self.mutex):
            # Vérifier si l'image est déjà en cache
            if image_path in self.cache:
                self._remove_item(image_path)
            
            # Ajouter au cache
            self.cache[image_path] = item
            self.current_memory_mb += file_size / (1024 * 1024)
            
            # Nettoyer le cache si nécessaire
            self._cleanup_cache()
            
            self.cacheUpdated.emit()
    
    def is_cached(self, image_path: str) -> bool:
        """Vérifie si une image est en cache."""
        with QMutexLocker(self.mutex):
            return image_path in self.cache
    
    def preload_images(self, image_paths: List[str], priority_paths: List[str] = None):
        """Précharge une liste d'images en arrière-plan."""
        if not self.preload_enabled:
            return
        
        # Arrêter le préchargeur précédent
        if self.preloader and self.preloader.isRunning():
            self.preloader.stop()
            self.preloader.wait()
        
        # Prioriser certaines images
        if priority_paths:
            priority_set = set(priority_paths)
            sorted_paths = []
            # Ajouter d'abord les images prioritaires
            for path in image_paths:
                if path in priority_set:
                    sorted_paths.append(path)
            # Puis les autres
            for path in image_paths:
                if path not in priority_set:
                    sorted_paths.append(path)
            image_paths = sorted_paths
        
        # Créer et démarrer le préchargeur
        self.preloader = ImagePreloader(image_paths, self)
        self.preloader.imageLoaded.connect(self._on_image_preloaded)
        self.preloader.loadingProgress.connect(self.preloadProgress)
        self.preloader.start()
    
    def stop_preloading(self):
        """Arrête le préchargement."""
        if self.preloader and self.preloader.isRunning():
            self.preloader.stop()
            self.preloader.wait()
    
    def _on_image_preloaded(self, image_path: str, image: QImage, pixmap: QPixmap):
        """Callback appelé quand une image est préchargée."""
        self.put_image(image_path, image, pixmap)
        self.stats['preloaded'] += 1
    
    def _remove_item(self, image_path: str):
        """Supprime un élément du cache."""
        if image_path in self.cache:
            item = self.cache[image_path]
            self.current_memory_mb -= item.file_size / (1024 * 1024)
            del self.cache[image_path]
            self.stats['evictions'] += 1
    
    def _cleanup_cache(self):
        """Nettoie le cache selon les limites définies."""
        # Nettoyer par nombre d'éléments
        while len(self.cache) > self.max_items:
            oldest_key = next(iter(self.cache))
            self._remove_item(oldest_key)
        
        # Nettoyer par mémoire
        while (self.current_memory_mb > self.max_memory_mb and 
               len(self.cache) > 1):
            oldest_key = next(iter(self.cache))
            self._remove_item(oldest_key)
    
    def clear_cache(self):
        """Vide complètement le cache."""
        with QMutexLocker(self.mutex):
            self.cache.clear()
            self.current_memory_mb = 0
            self.stats['evictions'] += len(self.cache)
            self.cacheUpdated.emit()
    
    def get_cache_stats(self) -> Dict:
        """Retourne les statistiques du cache."""
        with QMutexLocker(self.mutex):
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'items_count': len(self.cache),
                'memory_mb': round(self.current_memory_mb, 2),
                'max_memory_mb': self.max_memory_mb,
                'hit_rate': round(hit_rate, 2),
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'preloaded': self.stats['preloaded']
            }
    
    def set_memory_limit(self, max_memory_mb: int):
        """Définit la limite de mémoire du cache."""
        self.max_memory_mb = max_memory_mb
        self._cleanup_cache()
    
    def set_max_items(self, max_items: int):
        """Définit le nombre maximum d'éléments du cache."""
        self.max_items = max_items
        self._cleanup_cache()
    
    def enable_preloading(self, enabled: bool):
        """Active/désactive le préchargement."""
        self.preload_enabled = enabled
        if not enabled:
            self.stop_preloading()


# Instance globale du gestionnaire de cache
_cache_manager = None

def get_cache_manager() -> ImageCacheManager:
    """Retourne l'instance globale du gestionnaire de cache."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ImageCacheManager()
    return _cache_manager
