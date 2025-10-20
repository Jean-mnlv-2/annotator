#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
from typing import List, Optional, Dict, Callable, Any
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, PriorityQueue
import threading

try:
    from PyQt5.QtGui import QImage, QPixmap, QImageReader
    from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer
except ImportError:
    from PyQt4.QtGui import QImage, QPixmap, QImageReader
    from PyQt4.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer


class LoadTask:
    """Représente une tâche de chargement d'image."""
    
    def __init__(self, image_path: str, priority: int = 0, callback: Callable = None, 
                 metadata: Dict = None):
        self.image_path = image_path
        self.priority = priority  # Plus bas = plus prioritaire
        self.callback = callback
        self.metadata = metadata or {}
        self.created_time = time.time()
        self.retry_count = 0
        self.max_retries = 3
    
    def __lt__(self, other):
        """Pour la PriorityQueue - priorité plus basse = plus prioritaire."""
        return self.priority < other.priority


class ImageLoadResult:
    """Résultat d'un chargement d'image."""
    
    def __init__(self, image_path: str, success: bool, image: QImage = None, 
                 pixmap: QPixmap = None, error: str = None, metadata: Dict = None):
        self.image_path = image_path
        self.success = success
        self.image = image
        self.pixmap = pixmap
        self.error = error
        self.metadata = metadata or {}
        self.load_time = time.time()


class AsyncImageLoader(QObject):
    """
    Gestionnaire de chargement asynchrone d'images avec priorités et préchargement.
    """
    
    # Signaux
    imageLoaded = pyqtSignal(str, QImage, QPixmap)  # image_path, image, pixmap
    imageLoadFailed = pyqtSignal(str, str)  # image_path, error
    loadingProgress = pyqtSignal(str, int)  # image_name, progress_percent
    allImagesLoaded = pyqtSignal()
    
    def __init__(self, max_workers: int = 4, cache_manager=None):
        super().__init__()
        self.max_workers = max_workers
        self.cache_manager = cache_manager
        
        # Thread pool pour le chargement
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loading_futures: Dict[str, Future] = {}
        
        # Queue de tâches avec priorités
        self.task_queue = PriorityQueue()
        self.processing_queue = Queue()
        
        # État
        self.is_loading = False
        self.current_tasks = []
        self.total_tasks = 0
        self.completed_tasks = 0
        
        # Mutex pour la thread safety
        self.mutex = QMutex()
        
        # Timer pour traiter la queue
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self._process_queue)
        self.process_timer.start(100)  # Traiter toutes les 100ms
        
        # Statistiques
        self.stats = {
            'total_loaded': 0,
            'total_failed': 0,
            'cache_hits': 0,
            'average_load_time': 0.0
        }
        
        # Configuration
        self.enabled_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff', '.webp'}
        self.max_image_size = 50 * 1024 * 1024  # 50MB max par image
    
    def load_image(self, image_path: str, priority: int = 0, 
                   callback: Callable = None, metadata: Dict = None) -> bool:
        """
        Ajoute une image à la queue de chargement.
        
        Args:
            image_path: Chemin vers l'image
            priority: Priorité (0 = haute, 100 = basse)
            callback: Fonction à appeler quand l'image est chargée
            metadata: Métadonnées supplémentaires
        
        Returns:
            True si ajouté à la queue, False sinon
        """
        if not os.path.exists(image_path):
            self.imageLoadFailed.emit(image_path, "File does not exist")
            return False
        
        if not self._is_supported_format(image_path):
            self.imageLoadFailed.emit(image_path, "Unsupported image format")
            return False
        
        # Vérifier la taille du fichier
        try:
            file_size = os.path.getsize(image_path)
            if file_size > self.max_image_size:
                self.imageLoadFailed.emit(image_path, f"File too large: {file_size / (1024*1024):.1f}MB")
                return False
        except OSError:
            self.imageLoadFailed.emit(image_path, "Cannot access file")
            return False
        
        with QMutexLocker(self.mutex):
            # Vérifier si l'image est déjà en cours de chargement
            if image_path in self.loading_futures:
                return True
            
            # Vérifier le cache si disponible
            if self.cache_manager:
                cached_result = self.cache_manager.get_image(image_path)
                if cached_result:
                    image, pixmap = cached_result
                    self.imageLoaded.emit(image_path, image, pixmap)
                    self.stats['cache_hits'] += 1
                    return True
            
            # Créer la tâche de chargement
            task = LoadTask(image_path, priority, callback, metadata)
            self.task_queue.put(task)
            
            # Soumettre la tâche au thread pool
            future = self.executor.submit(self._load_image_worker, task)
            self.loading_futures[image_path] = future
            
            self.total_tasks += 1
        
        return True
    
    def load_images_batch(self, image_paths: List[str], priority: int = 0,
                         callback: Callable = None, metadata: Dict = None) -> int:
        """
        Charge plusieurs images en batch.
        
        Args:
            image_paths: Liste des chemins d'images
            priority: Priorité commune à toutes les images
            callback: Callback commun
            metadata: Métadonnées communes
        
        Returns:
            Nombre d'images ajoutées à la queue
        """
        added_count = 0
        
        for i, image_path in enumerate(image_paths):
            # Priorité décroissante pour les images du batch
            batch_priority = priority + i
            batch_metadata = metadata.copy() if metadata else {}
            batch_metadata['batch_index'] = i
            batch_metadata['batch_size'] = len(image_paths)
            
            if self.load_image(image_path, batch_priority, callback, batch_metadata):
                added_count += 1
        
        return added_count
    
    def preload_images(self, image_paths: List[str], current_index: int = 0,
                      lookahead: int = 5) -> int:
        """
        Précharge les images autour de l'index actuel.
        
        Args:
            image_paths: Liste complète des images
            current_index: Index de l'image actuelle
            lookahead: Nombre d'images à précharger de chaque côté
        
        Returns:
            Nombre d'images préchargées
        """
        preload_paths = []
        
        # Images avant l'index actuel
        start_idx = max(0, current_index - lookahead)
        for i in range(start_idx, current_index):
            preload_paths.append(image_paths[i])
        
        # Images après l'index actuel
        end_idx = min(len(image_paths), current_index + lookahead + 1)
        for i in range(current_index + 1, end_idx):
            preload_paths.append(image_paths[i])
        
        return self.load_images_batch(preload_paths, priority=50)
    
    def cancel_load(self, image_path: str) -> bool:
        """Annule le chargement d'une image."""
        with QMutexLocker(self.mutex):
            if image_path in self.loading_futures:
                future = self.loading_futures[image_path]
                future.cancel()
                del self.loading_futures[image_path]
                return True
        return False
    
    def cancel_all_loads(self):
        """Annule tous les chargements en cours."""
        with QMutexLocker(self.mutex):
            for future in self.loading_futures.values():
                future.cancel()
            self.loading_futures.clear()
            self.total_tasks = 0
            self.completed_tasks = 0
    
    def _load_image_worker(self, task: LoadTask) -> ImageLoadResult:
        """Worker qui charge une image dans un thread séparé."""
        start_time = time.time()
        
        try:
            # Charger l'image
            reader = QImageReader(task.image_path)
            reader.setAutoTransform(True)
            
            # Optimisations pour la performance
            reader.setScaledSize(QSize(4096, 4096))  # Limiter la taille maximale
            
            image = reader.read()
            
            if image.isNull():
                return ImageLoadResult(
                    task.image_path, False, 
                    error=f"Failed to read image: {reader.errorString()}",
                    metadata=task.metadata
                )
            
            # Créer le pixmap
            pixmap = QPixmap.fromImage(image)
            
            # Ajouter au cache si disponible
            if self.cache_manager:
                self.cache_manager.put_image(task.image_path, image, pixmap)
            
            load_time = time.time() - start_time
            
            # Émettre les signaux
            self.imageLoaded.emit(task.image_path, image, pixmap)
            
            # Appeler le callback si fourni
            if task.callback:
                try:
                    task.callback(task.image_path, image, pixmap, task.metadata)
                except Exception as e:
                    print(f"Callback error for {task.image_path}: {e}")
            
            # Mettre à jour les statistiques
            self._update_stats(load_time)
            
            return ImageLoadResult(
                task.image_path, True, image, pixmap, 
                metadata=task.metadata
            )
            
        except Exception as e:
            error_msg = f"Exception during loading: {str(e)}"
            self.imageLoadFailed.emit(task.image_path, error_msg)
            
            return ImageLoadResult(
                task.image_path, False, 
                error=error_msg,
                metadata=task.metadata
            )
        
        finally:
            # Nettoyer les références
            with QMutexLocker(self.mutex):
                if task.image_path in self.loading_futures:
                    del self.loading_futures[task.image_path]
                self.completed_tasks += 1
                
                # Vérifier si tous les chargements sont terminés
                if self.completed_tasks >= self.total_tasks and self.total_tasks > 0:
                    self.allImagesLoaded.emit()
    
    def _process_queue(self):
        """Traite la queue de tâches."""
        # Cette méthode est appelée par le timer pour traiter les tâches
        # Dans cette implémentation, les tâches sont directement soumises au thread pool
        pass
    
    def _is_supported_format(self, image_path: str) -> bool:
        """Vérifie si le format d'image est supporté."""
        ext = os.path.splitext(image_path)[1].lower()
        return ext in self.enabled_formats
    
    def _update_stats(self, load_time: float):
        """Met à jour les statistiques de chargement."""
        self.stats['total_loaded'] += 1
        
        # Moyenne mobile du temps de chargement
        total = self.stats['total_loaded']
        current_avg = self.stats['average_load_time']
        self.stats['average_load_time'] = (current_avg * (total - 1) + load_time) / total
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de chargement."""
        with QMutexLocker(self.mutex):
            return {
                'total_loaded': self.stats['total_loaded'],
                'total_failed': self.stats['total_failed'],
                'cache_hits': self.stats['cache_hits'],
                'average_load_time': round(self.stats['average_load_time'], 3),
                'active_loads': len(self.loading_futures),
                'queue_size': self.task_queue.qsize(),
                'completed_tasks': self.completed_tasks,
                'total_tasks': self.total_tasks
            }
    
    def set_max_workers(self, max_workers: int):
        """Définit le nombre maximum de workers."""
        self.max_workers = max_workers
        self.executor.shutdown(wait=True)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def set_max_image_size(self, max_size_mb: int):
        """Définit la taille maximale d'image en MB."""
        self.max_image_size = max_size_mb * 1024 * 1024
    
    def shutdown(self):
        """Arrête le loader et nettoie les ressources."""
        self.process_timer.stop()
        self.cancel_all_loads()
        self.executor.shutdown(wait=True)


class ProgressiveImageLoader(AsyncImageLoader):
    """
    Loader progressif qui charge les images en qualité réduite d'abord,
    puis améliore la qualité.
    """
    
    def __init__(self, max_workers: int = 4, cache_manager=None):
        super().__init__(max_workers, cache_manager)
        self.thumbnail_size = QSize(256, 256)
        self.full_quality_queue = Queue()
    
    def load_image_progressive(self, image_path: str, priority: int = 0,
                              callback: Callable = None, metadata: Dict = None) -> bool:
        """
        Charge une image de manière progressive (thumbnail d'abord, puis qualité complète).
        """
        # Charger d'abord le thumbnail
        thumbnail_metadata = metadata.copy() if metadata else {}
        thumbnail_metadata['progressive'] = True
        thumbnail_metadata['stage'] = 'thumbnail'
        
        def thumbnail_callback(path, image, pixmap, meta):
            # Émettre le thumbnail
            self.imageLoaded.emit(path, image, pixmap)
            
            # Ajouter la qualité complète à la queue
            full_metadata = meta.copy()
            full_metadata['stage'] = 'full_quality'
            self.full_quality_queue.put((path, 10, callback, full_metadata))
        
        return self.load_image(image_path, priority, thumbnail_callback, thumbnail_metadata)
    
    def _load_image_worker(self, task: LoadTask) -> ImageLoadResult:
        """Worker spécialisé pour le chargement progressif."""
        start_time = time.time()
        
        try:
            reader = QImageReader(task.image_path)
            reader.setAutoTransform(True)
            
            # Déterminer la taille cible selon le stage
            stage = task.metadata.get('stage', 'full_quality')
            if stage == 'thumbnail':
                reader.setScaledSize(self.thumbnail_size)
            
            image = reader.read()
            
            if image.isNull():
                return ImageLoadResult(
                    task.image_path, False,
                    error=f"Failed to read image: {reader.errorString()}",
                    metadata=task.metadata
                )
            
            pixmap = QPixmap.fromImage(image)
            
            # Ajouter au cache
            if self.cache_manager:
                self.cache_manager.put_image(task.image_path, image, pixmap)
            
            load_time = time.time() - start_time
            
            # Émettre les signaux
            self.imageLoaded.emit(task.image_path, image, pixmap)
            
            # Callback
            if task.callback:
                task.callback(task.image_path, image, pixmap, task.metadata)
            
            self._update_stats(load_time)
            
            return ImageLoadResult(
                task.image_path, True, image, pixmap,
                metadata=task.metadata
            )
            
        except Exception as e:
            error_msg = f"Exception during loading: {str(e)}"
            self.imageLoadFailed.emit(task.image_path, error_msg)
            
            return ImageLoadResult(
                task.image_path, False,
                error=error_msg,
                metadata=task.metadata
            )
        
        finally:
            with QMutexLocker(self.mutex):
                if task.image_path in self.loading_futures:
                    del self.loading_futures[task.image_path]
                self.completed_tasks += 1


# Instance globale du loader
_async_loader = None

def get_async_loader() -> AsyncImageLoader:
    """Retourne l'instance globale du loader asynchrone."""
    global _async_loader
    if _async_loader is None:
        from libs.image_cache import get_cache_manager
        _async_loader = AsyncImageLoader(cache_manager=get_cache_manager())
    return _async_loader
