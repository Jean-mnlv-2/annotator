#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gc
import psutil
import os
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict, deque
import weakref

try:
    from PyQt5.QtGui import QImage, QPixmap
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
except ImportError:
    from PyQt4.QtGui import QImage, QPixmap
    from PyQt4.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker


class MemoryUsage:
    """Classe pour surveiller l'utilisation mémoire."""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.last_gc_time = time.time()
        self.gc_interval = 30  # GC toutes les 30 secondes
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Retourne les statistiques d'utilisation mémoire."""
        try:
            memory_info = self.process.memory_info()
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),  # Mémoire physique
                'vms_mb': memory_info.vms / (1024 * 1024),  # Mémoire virtuelle
                'percent': self.process.memory_percent(),
                'available_mb': psutil.virtual_memory().available / (1024 * 1024)
            }
        except Exception:
            return {
                'rss_mb': 0,
                'vms_mb': 0,
                'percent': 0,
                'available_mb': 0
            }
    
    def should_gc(self) -> bool:
        """Détermine si un garbage collection est nécessaire."""
        current_time = time.time()
        if current_time - self.last_gc_time >= self.gc_interval:
            self.last_gc_time = current_time
            return True
        return False


class MemoryPool:
    """Pool d'objets pour éviter les allocations répétées."""
    
    def __init__(self, object_factory: Callable, initial_size: int = 10, max_size: int = 100):
        self.object_factory = object_factory
        self.max_size = max_size
        self.pool = deque()
        self.mutex = QMutex()
        
        # Pré-allouer des objets
        for _ in range(initial_size):
            self.pool.append(object_factory())
    
    def get(self) -> Any:
        """Récupère un objet du pool."""
        with QMutexLocker(self.mutex):
            if self.pool:
                return self.pool.popleft()
            else:
                return self.object_factory()
    
    def put(self, obj: Any):
        """Remet un objet dans le pool."""
        with QMutexLocker(self.mutex):
            if len(self.pool) < self.max_size:
                # Réinitialiser l'objet si nécessaire
                if hasattr(obj, 'reset'):
                    obj.reset()
                self.pool.append(obj)


class ObjectTracker:
    """Suivi des objets pour détecter les fuites mémoire."""
    
    def __init__(self):
        self.object_counts = defaultdict(int)
        self.object_sizes = defaultdict(int)
        self.mutex = QMutex()
    
    def track_object(self, obj_type: type, size_bytes: int = 0):
        """Enregistre un objet."""
        with QMutexLocker(self.mutex):
            self.object_counts[obj_type.__name__] += 1
            self.object_sizes[obj_type.__name__] += size_bytes
    
    def untrack_object(self, obj_type: type, size_bytes: int = 0):
        """Désenregistre un objet."""
        with QMutexLocker(self.mutex):
            self.object_counts[obj_type.__name__] -= 1
            self.object_sizes[obj_type.__name__] -= size_bytes
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de suivi."""
        with QMutexLocker(self.mutex):
            return {
                'counts': dict(self.object_counts),
                'sizes': dict(self.object_sizes)
            }


class MemoryManager(QObject):
    """
    Gestionnaire de mémoire intelligent pour optimiser l'utilisation mémoire.
    """
    
    # Signaux
    memoryWarning = pyqtSignal(str)  # Avertissement mémoire
    memoryCritical = pyqtSignal(str)  # Mémoire critique
    memoryFreed = pyqtSignal(int)  # Mémoire libérée (MB)
    gcRequested = pyqtSignal()  # Demande de GC
    
    def __init__(self, warning_threshold_mb: int = 800, critical_threshold_mb: int = 1200):
        super().__init__()
        
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        
        # Surveillance mémoire
        self.memory_usage = MemoryUsage()
        self.last_memory_check = time.time()
        self.check_interval = 5  # Vérifier toutes les 5 secondes
        
        # Pools d'objets
        self.image_pool = MemoryPool(lambda: QImage(), initial_size=5, max_size=20)
        self.pixmap_pool = MemoryPool(lambda: QPixmap(), initial_size=5, max_size=20)
        
        # Suivi des objets
        self.object_tracker = ObjectTracker()
        
        # Cache des objets récemment libérés
        self.recently_freed = deque(maxlen=100)
        
        # Timer pour la surveillance
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_memory)
        self.monitor_timer.start(1000)  # Vérifier chaque seconde
        
        # Statistiques
        self.stats = {
            'total_allocations': 0,
            'total_deallocations': 0,
            'peak_memory_mb': 0,
            'gc_count': 0,
            'memory_freed_mb': 0
        }
        
        # Callbacks de nettoyage
        self.cleanup_callbacks = []
        
        # État
        self.is_monitoring = True
        self.emergency_mode = False
    
    def _monitor_memory(self):
        """Surveille l'utilisation mémoire et déclenche des actions si nécessaire."""
        if not self.is_monitoring:
            return
        
        current_time = time.time()
        if current_time - self.last_memory_check < self.check_interval:
            return
        
        self.last_memory_check = current_time
        
        # Obtenir les statistiques mémoire
        memory_info = self.memory_usage.get_memory_usage()
        current_memory_mb = memory_info['rss_mb']
        
        # Mettre à jour le pic mémoire
        if current_memory_mb > self.stats['peak_memory_mb']:
            self.stats['peak_memory_mb'] = current_memory_mb
        
        # Vérifier les seuils
        if current_memory_mb >= self.critical_threshold_mb:
            self._handle_critical_memory()
        elif current_memory_mb >= self.warning_threshold_mb:
            self._handle_memory_warning(current_memory_mb)
        
        # Garbage collection périodique
        if self.memory_usage.should_gc():
            self._request_gc()
    
    def _handle_memory_warning(self, current_memory_mb: float):
        """Gère les avertissements mémoire."""
        warning_msg = f"Memory usage high: {current_memory_mb:.1f}MB"
        self.memoryWarning.emit(warning_msg)
        
        # Libérer les caches
        self._free_caches()
        
        # Demander un GC léger
        gc.collect()
        self.stats['gc_count'] += 1
    
    def _handle_critical_memory(self):
        """Gère la mémoire critique."""
        memory_info = self.memory_usage.get_memory_usage()
        critical_msg = f"Critical memory usage: {memory_info['rss_mb']:.1f}MB"
        self.memoryCritical.emit(critical_msg)
        
        self.emergency_mode = True
        
        # Libération d'urgence
        self._emergency_cleanup()
        
        # GC agressif
        for _ in range(3):
            gc.collect()
        
        self.stats['gc_count'] += 3
        self.emergency_mode = False
    
    def _free_caches(self):
        """Libère les caches non essentiels."""
        freed_mb = 0
        
        # Libérer les pools d'objets
        with self.image_pool.mutex:
            while self.image_pool.pool:
                obj = self.image_pool.pool.popleft()
                del obj
                freed_mb += 0.1  # Estimation
        
        with self.pixmap_pool.mutex:
            while self.pixmap_pool.pool:
                obj = self.pixmap_pool.pool.popleft()
                del obj
                freed_mb += 0.5  # Estimation
        
        # Appeler les callbacks de nettoyage
        for callback in self.cleanup_callbacks:
            try:
                callback_freed = callback()
                freed_mb += callback_freed
            except Exception as e:
                print(f"Cleanup callback error: {e}")
        
        if freed_mb > 0:
            self.stats['memory_freed_mb'] += freed_mb
            self.memoryFreed.emit(int(freed_mb))
    
    def _emergency_cleanup(self):
        """Nettoyage d'urgence en cas de mémoire critique."""
        # Forcer la libération de tous les caches
        self._free_caches()
        
        # Libérer les objets récemment libérés
        while self.recently_freed:
            self.recently_freed.popleft()
        
        # Appeler tous les callbacks de nettoyage d'urgence
        for callback in self.cleanup_callbacks:
            try:
                callback(emergency=True)
            except Exception:
                pass
    
    def _request_gc(self):
        """Demande un garbage collection."""
        self.gcRequested.emit()
        gc.collect()
    
    def register_cleanup_callback(self, callback: Callable[[bool], int]):
        """
        Enregistre un callback de nettoyage.
        
        Args:
            callback: Fonction qui retourne le nombre de MB libérés
                     Paramètre: emergency (bool)
        """
        self.cleanup_callbacks.append(callback)
    
    def unregister_cleanup_callback(self, callback: Callable):
        """Désenregistre un callback de nettoyage."""
        if callback in self.cleanup_callbacks:
            self.cleanup_callbacks.remove(callback)
    
    def get_image_from_pool(self) -> QImage:
        """Récupère une QImage du pool."""
        image = self.image_pool.get()
        self.object_tracker.track_object(QImage)
        self.stats['total_allocations'] += 1
        return image
    
    def return_image_to_pool(self, image: QImage):
        """Remet une QImage dans le pool."""
        if image:
            self.image_pool.put(image)
            self.object_tracker.untrack_object(QImage)
            self.stats['total_deallocations'] += 1
    
    def get_pixmap_from_pool(self) -> QPixmap:
        """Récupère une QPixmap du pool."""
        pixmap = self.pixmap_pool.get()
        self.object_tracker.track_object(QPixmap)
        self.stats['total_allocations'] += 1
        return pixmap
    
    def return_pixmap_to_pool(self, pixmap: QPixmap):
        """Remet une QPixmap dans le pool."""
        if pixmap:
            self.pixmap_pool.put(pixmap)
            self.object_tracker.untrack_object(QPixmap)
            self.stats['total_deallocations'] += 1
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques mémoire complètes."""
        memory_info = self.memory_usage.get_memory_usage()
        object_stats = self.object_tracker.get_stats()
        
        return {
            'memory_usage': memory_info,
            'thresholds': {
                'warning_mb': self.warning_threshold_mb,
                'critical_mb': self.critical_threshold_mb
            },
            'stats': self.stats,
            'object_tracking': object_stats,
            'pools': {
                'image_pool_size': len(self.image_pool.pool),
                'pixmap_pool_size': len(self.pixmap_pool.pool)
            },
            'emergency_mode': self.emergency_mode,
            'monitoring': self.is_monitoring
        }
    
    def set_thresholds(self, warning_mb: int, critical_mb: int):
        """Définit les seuils d'avertissement."""
        self.warning_threshold_mb = warning_mb
        self.critical_threshold_mb = critical_mb
    
    def set_monitoring(self, enabled: bool):
        """Active/désactive la surveillance."""
        self.is_monitoring = enabled
        if enabled:
            self.monitor_timer.start(1000)
        else:
            self.monitor_timer.stop()
    
    def force_cleanup(self):
        """Force un nettoyage complet."""
        self._free_caches()
        self._request_gc()
    
    def shutdown(self):
        """Arrête le gestionnaire de mémoire."""
        self.is_monitoring = False
        self.monitor_timer.stop()
        
        # Nettoyer les pools
        self.image_pool.pool.clear()
        self.pixmap_pool.pool.clear()
        
        # Nettoyer les callbacks
        self.cleanup_callbacks.clear()
        
        # GC final
        gc.collect()


class MemoryProfiler:
    """Profileur de mémoire pour le développement."""
    
    def __init__(self):
        self.snapshots = []
        self.memory_usage = MemoryUsage()
    
    def take_snapshot(self, label: str = None):
        """Prend un instantané de la mémoire."""
        memory_info = self.memory_usage.get_memory_usage()
        snapshot = {
            'timestamp': time.time(),
            'label': label or f"Snapshot {len(self.snapshots) + 1}",
            'memory_mb': memory_info['rss_mb'],
            'memory_percent': memory_info['percent']
        }
        self.snapshots.append(snapshot)
        return snapshot
    
    def compare_snapshots(self, index1: int, index2: int) -> Dict[str, float]:
        """Compare deux instantanés."""
        if not (0 <= index1 < len(self.snapshots) and 0 <= index2 < len(self.snapshots)):
            return {}
        
        snap1 = self.snapshots[index1]
        snap2 = self.snapshots[index2]
        
        return {
            'memory_diff_mb': snap2['memory_mb'] - snap1['memory_mb'],
            'memory_diff_percent': snap2['memory_percent'] - snap1['memory_percent'],
            'time_diff_seconds': snap2['timestamp'] - snap1['timestamp']
        }
    
    def get_snapshots(self) -> List[Dict]:
        """Retourne tous les instantanés."""
        return self.snapshots.copy()
    
    def clear_snapshots(self):
        """Efface tous les instantanés."""
        self.snapshots.clear()


# Instance globale du gestionnaire de mémoire
_memory_manager = None

def get_memory_manager() -> MemoryManager:
    """Retourne l'instance globale du gestionnaire de mémoire."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def get_memory_profiler() -> MemoryProfiler:
    """Retourne une instance du profileur de mémoire."""
    return MemoryProfiler()
