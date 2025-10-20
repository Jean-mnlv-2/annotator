#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
from typing import List, Optional, Dict, Any, Callable, Tuple
from collections import deque
from enum import Enum

try:
    from PyQt5.QtGui import QPixmap, QImage
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt5.QtWidgets import QWidget, QApplication
except ImportError:
    from PyQt4.QtGui import QPixmap, QImage, QWidget, QApplication
    from PyQt4.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker


class NavigationMode(Enum):
    """Modes de navigation."""
    SEQUENTIAL = "sequential"      # Navigation séquentielle
    RANDOM = "random"             # Navigation aléatoire
    FILTERED = "filtered"         # Navigation filtrée
    SMART = "smart"              # Navigation intelligente


class ImageInfo:
    """Informations sur une image."""
    
    def __init__(self, path: str, index: int, metadata: Dict[str, Any] = None):
        self.path = path
        self.index = index
        self.metadata = metadata or {}
        self.thumbnail = None
        self.last_accessed = time.time()
        self.access_count = 0
        self.is_annotated = False
        self.is_verified = False
        self.has_errors = False
        self.file_size = 0
        self.modification_time = 0
        
        # Charger les métadonnées de base
        self._load_basic_info()
    
    def _load_basic_info(self):
        """Charge les informations de base du fichier."""
        try:
            if os.path.exists(self.path):
                stat = os.stat(self.path)
                self.file_size = stat.st_size
                self.modification_time = stat.st_mtime
        except OSError:
            self.has_errors = True
    
    def update_access(self):
        """Met à jour les informations d'accès."""
        self.last_accessed = time.time()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'path': self.path,
            'index': self.index,
            'metadata': self.metadata,
            'last_accessed': self.last_accessed,
            'access_count': self.access_count,
            'is_annotated': self.is_annotated,
            'is_verified': self.is_verified,
            'has_errors': self.has_errors,
            'file_size': self.file_size,
            'modification_time': self.modification_time
        }


class NavigationHistory:
    """Historique de navigation."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.history = deque(maxlen=max_size)
        self.current_index = -1
        self.mutex = QMutex()
    
    def add_image(self, image_info: ImageInfo):
        """Ajoute une image à l'historique."""
        with QMutexLocker(self.mutex):
            # Supprimer les éléments après l'index actuel si on navigue depuis le milieu
            if self.current_index < len(self.history) - 1:
                self.history = deque(list(self.history)[:self.current_index + 1], maxlen=self.max_size)
            
            # Ajouter la nouvelle image
            self.history.append(image_info)
            self.current_index = len(self.history) - 1
    
    def can_go_back(self) -> bool:
        """Vérifie si on peut revenir en arrière."""
        with QMutexLocker(self.mutex):
            return self.current_index > 0
    
    def can_go_forward(self) -> bool:
        """Vérifie si on peut aller en avant."""
        with QMutexLocker(self.mutex):
            return self.current_index < len(self.history) - 1
    
    def go_back(self) -> Optional[ImageInfo]:
        """Va à l'image précédente."""
        with QMutexLocker(self.mutex):
            if self.can_go_back():
                self.current_index -= 1
                return self.history[self.current_index]
        return None
    
    def go_forward(self) -> Optional[ImageInfo]:
        """Va à l'image suivante."""
        with QMutexLocker(self.mutex):
            if self.can_go_forward():
                self.current_index += 1
                return self.history[self.current_index]
        return None
    
    def get_current(self) -> Optional[ImageInfo]:
        """Retourne l'image actuelle."""
        with QMutexLocker(self.mutex):
            if 0 <= self.current_index < len(self.history):
                return self.history[self.current_index]
        return None
    
    def get_all(self) -> List[ImageInfo]:
        """Retourne tout l'historique."""
        with QMutexLocker(self.mutex):
            return list(self.history)
    
    def clear(self):
        """Vide l'historique."""
        with QMutexLocker(self.mutex):
            self.history.clear()
            self.current_index = -1


class ImageFilter:
    """Filtre pour les images."""
    
    def __init__(self):
        self.conditions = []
        self.enabled = True
    
    def add_condition(self, condition: Callable[[ImageInfo], bool], description: str = ""):
        """Ajoute une condition de filtrage."""
        self.conditions.append({
            'condition': condition,
            'description': description
        })
    
    def matches(self, image_info: ImageInfo) -> bool:
        """Vérifie si une image correspond aux filtres."""
        if not self.enabled or not self.conditions:
            return True
        
        return all(condition['condition'](image_info) for condition in self.conditions)
    
    def get_matching_images(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """Retourne les images qui correspondent aux filtres."""
        return [img for img in images if self.matches(img)]
    
    def clear_conditions(self):
        """Efface toutes les conditions."""
        self.conditions.clear()
    
    def set_enabled(self, enabled: bool):
        """Active/désactive le filtre."""
        self.enabled = enabled


class SmartNavigator:
    """Navigateur intelligent basé sur l'IA."""
    
    def __init__(self):
        self.preferences = {
            'prioritize_unannotated': True,
            'prioritize_unverified': True,
            'avoid_errors': True,
            'prefer_recent': False,
            'balance_workload': True
        }
        self.learning_data = {}
        self.smart_suggestions = []
    
    def get_next_suggestion(self, current_images: List[ImageInfo], 
                           current_index: int) -> Optional[int]:
        """Suggère la prochaine image à annoter."""
        if not current_images:
            return None
        
        # Calculer les scores pour chaque image
        scores = []
        for i, img in enumerate(current_images):
            score = self._calculate_smart_score(img, i, current_index)
            scores.append((i, score))
        
        # Trier par score (plus haut = plus prioritaire)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Retourner l'index de l'image avec le meilleur score
        if scores:
            return scores[0][0]
        
        return None
    
    def _calculate_smart_score(self, img: ImageInfo, index: int, current_index: int) -> float:
        """Calcule un score intelligent pour une image."""
        score = 0.0
        
        # Priorité aux images non annotées
        if self.preferences['prioritize_unannotated'] and not img.is_annotated:
            score += 10.0
        
        # Priorité aux images non vérifiées
        if self.preferences['prioritize_unverified'] and not img.is_verified:
            score += 5.0
        
        # Éviter les images avec erreurs
        if self.preferences['avoid_errors'] and img.has_errors:
            score -= 20.0
        
        # Préférer les images récentes
        if self.preferences['prefer_recent']:
            days_since_modification = (time.time() - img.modification_time) / (24 * 3600)
            score += max(0, 5.0 - days_since_modification)
        
        # Équilibrer la charge de travail
        if self.preferences['balance_workload']:
            # Réduire le score pour les images déjà visitées
            if img.access_count > 0:
                score -= min(5.0, img.access_count * 0.5)
        
        # Bonus pour les images proches de la position actuelle
        distance = abs(index - current_index)
        if distance < 10:
            score += max(0, 3.0 - distance * 0.3)
        
        return score
    
    def learn_from_behavior(self, image_info: ImageInfo, action: str, duration: float):
        """Apprend du comportement de l'utilisateur."""
        key = f"{image_info.path}:{action}"
        
        if key not in self.learning_data:
            self.learning_data[key] = {
                'count': 0,
                'total_duration': 0.0,
                'avg_duration': 0.0
            }
        
        data = self.learning_data[key]
        data['count'] += 1
        data['total_duration'] += duration
        data['avg_duration'] = data['total_duration'] / data['count']
    
    def update_preferences(self, preferences: Dict[str, Any]):
        """Met à jour les préférences."""
        self.preferences.update(preferences)


class NavigationManager(QObject):
    """
    Gestionnaire de navigation amélioré entre les images.
    """
    
    # Signaux
    currentImageChanged = pyqtSignal(ImageInfo)
    navigationModeChanged = pyqtSignal(NavigationMode)
    imageListChanged = pyqtSignal(list)  # List[ImageInfo]
    filterChanged = pyqtSignal()
    historyChanged = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        self.images: List[ImageInfo] = []
        self.current_index = -1
        self.navigation_mode = NavigationMode.SEQUENTIAL
        
        # Composants
        self.history = NavigationHistory()
        self.filter = ImageFilter()
        self.smart_navigator = SmartNavigator()
        
        # Configuration
        self.auto_advance = False
        self.loop_mode = False
        self.preload_count = 3
        
        # État
        self.is_navigating = False
        self.last_navigation_time = 0
        self.navigation_stats = {
            'total_navigations': 0,
            'back_navigations': 0,
            'forward_navigations': 0,
            'jump_navigations': 0,
            'filter_navigations': 0
        }
        
        # Timer pour les mises à jour
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(10000)  # Mettre à jour toutes les 10 secondes
    
    def set_image_list(self, image_paths: List[str], start_index: int = 0):
        """Définit la liste des images."""
        self.images.clear()
        
        for i, path in enumerate(image_paths):
            image_info = ImageInfo(path, i)
            self.images.append(image_info)
        
        self.current_index = max(0, min(start_index, len(self.images) - 1))
        
        # Mettre à jour l'historique
        if self.images:
            self.history.add_image(self.images[self.current_index])
        
        self.imageListChanged.emit(self.images)
        
        # Émettre le signal pour l'image actuelle
        if self.images:
            self.currentImageChanged.emit(self.images[self.current_index])
    
    def add_image(self, path: str, index: Optional[int] = None) -> bool:
        """Ajoute une image à la liste."""
        if not os.path.exists(path):
            return False
        
        if index is None:
            index = len(self.images)
        
        image_info = ImageInfo(path, index)
        self.images.insert(index, image_info)
        
        # Ajuster les index
        for i in range(index + 1, len(self.images)):
            self.images[i].index = i
        
        # Ajuster l'index actuel si nécessaire
        if index <= self.current_index:
            self.current_index += 1
        
        self.imageListChanged.emit(self.images)
        return True
    
    def remove_image(self, index: int) -> bool:
        """Supprime une image de la liste."""
        if 0 <= index < len(self.images):
            del self.images[index]
            
            # Ajuster les index
            for i in range(index, len(self.images)):
                self.images[i].index = i
            
            # Ajuster l'index actuel si nécessaire
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index:
                # Si on supprime l'image actuelle, aller à la suivante ou précédente
                if self.current_index >= len(self.images):
                    self.current_index = len(self.images) - 1
                
                if self.current_index >= 0:
                    self.currentImageChanged.emit(self.images[self.current_index])
            
            self.imageListChanged.emit(self.images)
            return True
        
        return False
    
    def navigate_to(self, index: int) -> bool:
        """Navigue vers une image spécifique."""
        if not 0 <= index < len(self.images):
            return False
        
        self.current_index = index
        current_image = self.images[index]
        
        # Mettre à jour l'historique
        self.history.add_image(current_image)
        
        # Mettre à jour les statistiques d'accès
        current_image.update_access()
        
        # Émettre les signaux
        self.currentImageChanged.emit(current_image)
        self.historyChanged.emit()
        
        # Mettre à jour les statistiques
        self.navigation_stats['jump_navigations'] += 1
        self.navigation_stats['total_navigations'] += 1
        self.last_navigation_time = time.time()
        
        return True
    
    def navigate_next(self) -> bool:
        """Navigue vers l'image suivante."""
        if not self.images:
            return False
        
        if self.navigation_mode == NavigationMode.SEQUENTIAL:
            return self._navigate_sequential(1)
        elif self.navigation_mode == NavigationMode.RANDOM:
            return self._navigate_random()
        elif self.navigation_mode == NavigationMode.FILTERED:
            return self._navigate_filtered(1)
        elif self.navigation_mode == NavigationMode.SMART:
            return self._navigate_smart(1)
        
        return False
    
    def navigate_previous(self) -> bool:
        """Navigue vers l'image précédente."""
        if not self.images:
            return False
        
        if self.navigation_mode == NavigationMode.SEQUENTIAL:
            return self._navigate_sequential(-1)
        elif self.navigation_mode == NavigationMode.FILTERED:
            return self._navigate_filtered(-1)
        elif self.navigation_mode == NavigationMode.SMART:
            return self._navigate_smart(-1)
        
        # Pour le mode random, on utilise l'historique
        return self._navigate_history_back()
    
    def _navigate_sequential(self, direction: int) -> bool:
        """Navigation séquentielle."""
        new_index = self.current_index + direction
        
        if self.loop_mode:
            new_index = new_index % len(self.images)
        else:
            new_index = max(0, min(new_index, len(self.images) - 1))
        
        if new_index != self.current_index:
            return self.navigate_to(new_index)
        
        return False
    
    def _navigate_random(self) -> bool:
        """Navigation aléatoire."""
        if len(self.images) <= 1:
            return False
        
        import random
        available_indices = [i for i in range(len(self.images)) if i != self.current_index]
        
        if available_indices:
            new_index = random.choice(available_indices)
            return self.navigate_to(new_index)
        
        return False
    
    def _navigate_filtered(self, direction: int) -> bool:
        """Navigation filtrée."""
        filtered_images = self.filter.get_matching_images(self.images)
        
        if not filtered_images:
            return False
        
        # Trouver l'index dans la liste filtrée
        current_filtered_index = -1
        for i, img in enumerate(filtered_images):
            if img.index == self.current_index:
                current_filtered_index = i
                break
        
        new_filtered_index = current_filtered_index + direction
        
        if 0 <= new_filtered_index < len(filtered_images):
            new_index = filtered_images[new_filtered_index].index
            self.navigation_stats['filter_navigations'] += 1
            return self.navigate_to(new_index)
        
        return False
    
    def _navigate_smart(self, direction: int) -> bool:
        """Navigation intelligente."""
        suggestion = self.smart_navigator.get_next_suggestion(self.images, self.current_index)
        
        if suggestion is not None and suggestion != self.current_index:
            return self.navigate_to(suggestion)
        
        # Fallback vers navigation séquentielle
        return self._navigate_sequential(direction)
    
    def _navigate_history_back(self) -> bool:
        """Navigation via l'historique (retour)."""
        previous_image = self.history.go_back()
        
        if previous_image:
            # Trouver l'index dans la liste actuelle
            for i, img in enumerate(self.images):
                if img.path == previous_image.path:
                    self.current_index = i
                    self.currentImageChanged.emit(img)
                    self.historyChanged.emit()
                    
                    self.navigation_stats['back_navigations'] += 1
                    self.navigation_stats['total_navigations'] += 1
                    return True
        
        return False
    
    def navigate_history_forward(self) -> bool:
        """Navigation via l'historique (avancer)."""
        next_image = self.history.go_forward()
        
        if next_image:
            # Trouver l'index dans la liste actuelle
            for i, img in enumerate(self.images):
                if img.path == next_image.path:
                    self.current_index = i
                    self.currentImageChanged.emit(img)
                    self.historyChanged.emit()
                    
                    self.navigation_stats['forward_navigations'] += 1
                    self.navigation_stats['total_navigations'] += 1
                    return True
        
        return False
    
    def navigate_first(self) -> bool:
        """Navigue vers la première image."""
        if self.images:
            return self.navigate_to(0)
        return False
    
    def navigate_last(self) -> bool:
        """Navigue vers la dernière image."""
        if self.images:
            return self.navigate_to(len(self.images) - 1)
        return False
    
    def set_navigation_mode(self, mode: NavigationMode):
        """Définit le mode de navigation."""
        if mode != self.navigation_mode:
            self.navigation_mode = mode
            self.navigationModeChanged.emit(mode)
    
    def set_filter(self, filter_obj: ImageFilter):
        """Définit le filtre d'images."""
        self.filter = filter_obj
        self.filterChanged.emit()
    
    def add_filter_condition(self, condition: Callable[[ImageInfo], bool], description: str = ""):
        """Ajoute une condition de filtrage."""
        self.filter.add_condition(condition, description)
        self.filterChanged.emit()
    
    def clear_filters(self):
        """Efface tous les filtres."""
        self.filter.clear_conditions()
        self.filterChanged.emit()
    
    def get_current_image(self) -> Optional[ImageInfo]:
        """Retourne l'image actuelle."""
        if 0 <= self.current_index < len(self.images):
            return self.images[self.current_index]
        return None
    
    def get_image_count(self) -> int:
        """Retourne le nombre d'images."""
        return len(self.images)
    
    def get_filtered_count(self) -> int:
        """Retourne le nombre d'images filtrées."""
        return len(self.filter.get_matching_images(self.images))
    
    def get_navigation_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de navigation."""
        return {
            'total_images': len(self.images),
            'current_index': self.current_index,
            'filtered_count': self.get_filtered_count(),
            'navigation_mode': self.navigation_mode.value,
            'history_size': len(self.history.get_all()),
            'can_go_back': self.history.can_go_back(),
            'can_go_forward': self.history.can_go_forward(),
            'stats': self.navigation_stats.copy()
        }
    
    def get_smart_suggestions(self, count: int = 5) -> List[ImageInfo]:
        """Retourne des suggestions intelligentes."""
        suggestions = []
        current_images = [img for img in self.images if img.index != self.current_index]
        
        for _ in range(min(count, len(current_images))):
            suggestion_index = self.smart_navigator.get_next_suggestion(current_images, self.current_index)
            if suggestion_index is not None:
                suggestions.append(current_images[suggestion_index])
                current_images.pop(suggestion_index)
        
        return suggestions
    
    def _update_stats(self):
        """Met à jour les statistiques périodiquement."""
        # Cette méthode peut être étendue pour des mises à jour automatiques
        pass
    
    def shutdown(self):
        """Arrête le gestionnaire."""
        self.update_timer.stop()
        
        # Sauvegarder les données d'apprentissage
        # (implémentation spécifique selon les besoins)


# Instance globale du gestionnaire de navigation
_navigation_manager = None

def get_navigation_manager() -> NavigationManager:
    """Retourne l'instance globale du gestionnaire de navigation."""
    global _navigation_manager
    if _navigation_manager is None:
        _navigation_manager = NavigationManager()
    return _navigation_manager
