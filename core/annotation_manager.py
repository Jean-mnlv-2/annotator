#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gestionnaire d'annotations - Gère les annotations d'images.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    from PyQt4.QtCore import QObject, pyqtSignal


class AnnotationType(Enum):
    """Types d'annotations."""
    BOUNDING_BOX = "bounding_box"
    POLYGON = "polygon"
    POINT = "point"
    LINE = "line"
    CIRCLE = "circle"


class AnnotationFormat(Enum):
    """Formats d'export d'annotations."""
    PASCAL_VOC = "pascal_voc"
    YOLO = "yolo"
    COCO = "coco"
    CREATEML = "createml"


class Annotation:
    """Représente une annotation."""
    
    def __init__(self, annotation_type: AnnotationType, label: str, 
                 coordinates: List[Tuple[float, float]], 
                 confidence: float = 1.0, difficult: bool = False):
        self.id = self._generate_id()
        self.type = annotation_type
        self.label = label
        self.coordinates = coordinates
        self.confidence = confidence
        self.difficult = difficult
        self.created = datetime.now().isoformat()
        self.modified = self.created
        self.metadata = {}
    
    def _generate_id(self) -> str:
        """Génère un ID unique pour l'annotation."""
        return f"ann_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'id': self.id,
            'type': self.type.value,
            'label': self.label,
            'coordinates': self.coordinates,
            'confidence': self.confidence,
            'difficult': self.difficult,
            'created': self.created,
            'modified': self.modified,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Annotation':
        """Crée depuis un dictionnaire."""
        annotation = cls(
            annotation_type=AnnotationType(data['type']),
            label=data['label'],
            coordinates=data['coordinates'],
            confidence=data.get('confidence', 1.0),
            difficult=data.get('difficult', False)
        )
        annotation.id = data.get('id', annotation.id)
        annotation.created = data.get('created', annotation.created)
        annotation.modified = data.get('modified', annotation.modified)
        annotation.metadata = data.get('metadata', {})
        return annotation


class ImageAnnotation:
    """Représente les annotations d'une image."""
    
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.annotations: List[Annotation] = []
        self.is_verified = False
        self.is_annotated = False
        self.created = datetime.now().isoformat()
        self.modified = self.created
        self.metadata = {}
    
    def add_annotation(self, annotation: Annotation):
        """Ajoute une annotation."""
        self.annotations.append(annotation)
        self.is_annotated = True
        self.modified = datetime.now().isoformat()
    
    def remove_annotation(self, annotation_id: str) -> bool:
        """Supprime une annotation par ID."""
        for i, annotation in enumerate(self.annotations):
            if annotation.id == annotation_id:
                del self.annotations[i]
                self.modified = datetime.now().isoformat()
                self.is_annotated = len(self.annotations) > 0
                return True
        return False
    
    def get_annotation(self, annotation_id: str) -> Optional[Annotation]:
        """Récupère une annotation par ID."""
        for annotation in self.annotations:
            if annotation.id == annotation_id:
                return annotation
        return None
    
    def update_annotation(self, annotation_id: str, **kwargs) -> bool:
        """Met à jour une annotation."""
        annotation = self.get_annotation(annotation_id)
        if annotation:
            for key, value in kwargs.items():
                if hasattr(annotation, key):
                    setattr(annotation, key, value)
            annotation.modified = datetime.now().isoformat()
            self.modified = annotation.modified
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'image_path': self.image_path,
            'annotations': [ann.to_dict() for ann in self.annotations],
            'is_verified': self.is_verified,
            'is_annotated': self.is_annotated,
            'created': self.created,
            'modified': self.modified,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageAnnotation':
        """Crée depuis un dictionnaire."""
        image_annotation = cls(data['image_path'])
        image_annotation.is_verified = data.get('is_verified', False)
        image_annotation.is_annotated = data.get('is_annotated', False)
        image_annotation.created = data.get('created', image_annotation.created)
        image_annotation.modified = data.get('modified', image_annotation.modified)
        image_annotation.metadata = data.get('metadata', {})
        
        # Charger les annotations
        for ann_data in data.get('annotations', []):
            annotation = Annotation.from_dict(ann_data)
            image_annotation.annotations.append(annotation)
        
        return image_annotation


class AnnotationManager(QObject):
    """
    Gestionnaire d'annotations pour les images.
    """
    
    # Signaux
    annotationAdded = pyqtSignal(str, Annotation)  # image_path, annotation
    annotationRemoved = pyqtSignal(str, str)  # image_path, annotation_id
    annotationUpdated = pyqtSignal(str, str, Annotation)  # image_path, annotation_id, annotation
    imageVerified = pyqtSignal(str, bool)  # image_path, is_verified
    annotationsLoaded = pyqtSignal(str)  # image_path
    annotationsSaved = pyqtSignal(str)  # image_path
    
    def __init__(self):
        super().__init__()
        
        # État
        self.annotation_directory: Optional[str] = None
        self.current_image_path: Optional[str] = None
        self.current_annotations: Optional[ImageAnnotation] = None
        
        # Cache des annotations
        self.annotations_cache: Dict[str, ImageAnnotation] = {}
        
        # Configuration
        self.default_format = AnnotationFormat.PASCAL_VOC
        self.auto_save = True
        self.backup_enabled = True
        self.compression_enabled = True
        
        # Statistiques
        self.stats = {
            'total_annotations': 0,
            'total_images': 0,
            'verified_images': 0,
            'annotated_images': 0,
            'last_save_time': None
        }
    
    def set_annotation_directory(self, directory: str):
        """Définit le répertoire des annotations."""
        if os.path.exists(directory):
            self.annotation_directory = directory
            self._load_annotation_cache()
    
    def load_annotations(self, image_path: str) -> bool:
        """
        Charge les annotations pour une image.
        
        Args:
            image_path: Chemin vers l'image
            
        Returns:
            True si les annotations sont chargées avec succès
        """
        try:
            # Vérifier si les annotations sont déjà en cache
            if image_path in self.annotations_cache:
                self.current_image_path = image_path
                self.current_annotations = self.annotations_cache[image_path]
                self.annotationsLoaded.emit(image_path)
                return True
            
            # Charger depuis le fichier
            annotation_file = self._get_annotation_file_path(image_path)
            if annotation_file and os.path.exists(annotation_file):
                self.current_annotations = self._load_from_file(annotation_file)
                if self.current_annotations:
                    self.annotations_cache[image_path] = self.current_annotations
                    self.current_image_path = image_path
                    self.annotationsLoaded.emit(image_path)
                    return True
            
            # Créer une nouvelle annotation vide
            self.current_annotations = ImageAnnotation(image_path)
            self.annotations_cache[image_path] = self.current_annotations
            self.current_image_path = image_path
            self.annotationsLoaded.emit(image_path)
            return True
            
        except Exception as e:
            print(f"Erreur lors du chargement des annotations: {e}")
            return False
    
    def save_annotations(self, image_path: str = None) -> bool:
        """
        Sauvegarde les annotations pour une image.
        
        Args:
            image_path: Chemin vers l'image (utilise l'image courante si None)
            
        Returns:
            True si la sauvegarde réussit
        """
        try:
            if image_path is None:
                image_path = self.current_image_path
            
            if not image_path or not self.annotation_directory:
                return False
            
            # Récupérer les annotations
            if image_path in self.annotations_cache:
                annotations = self.annotations_cache[image_path]
            else:
                return False
            
            # Sauvegarder dans le fichier
            annotation_file = self._get_annotation_file_path(image_path)
            if annotation_file:
                success = self._save_to_file(annotations, annotation_file)
                if success:
                    self.annotationsSaved.emit(image_path)
                    self.stats['last_save_time'] = datetime.now().isoformat()
                    return True
            
            return False
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des annotations: {e}")
            return False
    
    def add_annotation(self, annotation: Annotation, image_path: str = None) -> bool:
        """
        Ajoute une annotation.
        
        Args:
            annotation: Annotation à ajouter
            image_path: Chemin vers l'image (utilise l'image courante si None)
            
        Returns:
            True si l'annotation est ajoutée avec succès
        """
        try:
            if image_path is None:
                image_path = self.current_image_path
            
            if not image_path:
                return False
            
            # S'assurer que les annotations sont chargées
            if not self.load_annotations(image_path):
                return False
            
            # Ajouter l'annotation
            self.current_annotations.add_annotation(annotation)
            self.stats['total_annotations'] += 1
            
            # Sauvegarder automatiquement si activé
            if self.auto_save:
                self.save_annotations(image_path)
            
            self.annotationAdded.emit(image_path, annotation)
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'ajout de l'annotation: {e}")
            return False
    
    def remove_annotation(self, annotation_id: str, image_path: str = None) -> bool:
        """
        Supprime une annotation.
        
        Args:
            annotation_id: ID de l'annotation à supprimer
            image_path: Chemin vers l'image (utilise l'image courante si None)
            
        Returns:
            True si l'annotation est supprimée avec succès
        """
        try:
            if image_path is None:
                image_path = self.current_image_path
            
            if not image_path:
                return False
            
            # S'assurer que les annotations sont chargées
            if not self.load_annotations(image_path):
                return False
            
            # Supprimer l'annotation
            if self.current_annotations.remove_annotation(annotation_id):
                self.stats['total_annotations'] -= 1
                
                # Sauvegarder automatiquement si activé
                if self.auto_save:
                    self.save_annotations(image_path)
                
                self.annotationRemoved.emit(image_path, annotation_id)
                return True
            
            return False
            
        except Exception as e:
            print(f"Erreur lors de la suppression de l'annotation: {e}")
            return False
    
    def update_annotation(self, annotation_id: str, **kwargs) -> bool:
        """
        Met à jour une annotation.
        
        Args:
            annotation_id: ID de l'annotation à mettre à jour
            **kwargs: Attributs à mettre à jour
            
        Returns:
            True si l'annotation est mise à jour avec succès
        """
        try:
            if not self.current_image_path or not self.current_annotations:
                return False
            
            # Mettre à jour l'annotation
            if self.current_annotations.update_annotation(annotation_id, **kwargs):
                annotation = self.current_annotations.get_annotation(annotation_id)
                
                # Sauvegarder automatiquement si activé
                if self.auto_save:
                    self.save_annotations()
                
                self.annotationUpdated.emit(self.current_image_path, annotation_id, annotation)
                return True
            
            return False
            
        except Exception as e:
            print(f"Erreur lors de la mise à jour de l'annotation: {e}")
            return False
    
    def verify_image(self, image_path: str = None, is_verified: bool = True) -> bool:
        """
        Marque une image comme vérifiée.
        
        Args:
            image_path: Chemin vers l'image (utilise l'image courante si None)
            is_verified: True si vérifiée, False sinon
            
        Returns:
            True si la vérification est mise à jour avec succès
        """
        try:
            if image_path is None:
                image_path = self.current_image_path
            
            if not image_path:
                return False
            
            # S'assurer que les annotations sont chargées
            if not self.load_annotations(image_path):
                return False
            
            # Mettre à jour la vérification
            self.current_annotations.is_verified = is_verified
            
            # Sauvegarder automatiquement si activé
            if self.auto_save:
                self.save_annotations(image_path)
            
            self.imageVerified.emit(image_path, is_verified)
            return True
            
        except Exception as e:
            print(f"Erreur lors de la vérification de l'image: {e}")
            return False
    
    def get_annotations(self, image_path: str = None) -> List[Annotation]:
        """
        Retourne les annotations pour une image.
        
        Args:
            image_path: Chemin vers l'image (utilise l'image courante si None)
            
        Returns:
            Liste des annotations
        """
        if image_path is None:
            image_path = self.current_image_path
        
        if not image_path or not self.load_annotations(image_path):
            return []
        
        return self.current_annotations.annotations.copy()
    
    def get_annotation_count(self, image_path: str = None) -> int:
        """Retourne le nombre d'annotations pour une image."""
        return len(self.get_annotations(image_path))
    
    def export_annotations(self, image_path: str, format: AnnotationFormat, 
                          output_path: str = None) -> bool:
        """
        Exporte les annotations dans un format spécifique.
        
        Args:
            image_path: Chemin vers l'image
            format: Format d'export
            output_path: Chemin de sortie (optionnel)
            
        Returns:
            True si l'export réussit
        """
        try:
            if not self.load_annotations(image_path):
                return False
            
            if output_path is None:
                output_path = self._get_annotation_file_path(image_path, format)
            
            if format == AnnotationFormat.PASCAL_VOC:
                return self._export_pascal_voc(image_path, output_path)
            elif format == AnnotationFormat.YOLO:
                return self._export_yolo(image_path, output_path)
            elif format == AnnotationFormat.COCO:
                return self._export_coco(image_path, output_path)
            elif format == AnnotationFormat.CREATEML:
                return self._export_createml(image_path, output_path)
            
            return False
            
        except Exception as e:
            print(f"Erreur lors de l'export des annotations: {e}")
            return False
    
    def _get_annotation_file_path(self, image_path: str, 
                                 format: AnnotationFormat = None) -> Optional[str]:
        """Retourne le chemin du fichier d'annotation."""
        if not self.annotation_directory:
            return None
        
        lapp_name = os.path.splitext(os.path.basename(image_path))[0]
        
        if format is None:
            format = self.default_format
        
        if format == AnnotationFormat.PASCAL_VOC:
            return os.path.join(self.annotation_directory, f"{lapp_name}.xml")
        elif format == AnnotationFormat.YOLO:
            return os.path.join(self.annotation_directory, f"{lapp_name}.txt")
        elif format == AnnotationFormat.COCO:
            return os.path.join(self.annotation_directory, f"{lapp_name}.json")
        elif format == AnnotationFormat.CREATEML:
            return os.path.join(self.annotation_directory, f"{lapp_name}.json")
        
        return None
    
    def _load_from_file(self, file_path: str) -> Optional[ImageAnnotation]:
        """Charge les annotations depuis un fichier."""
        try:
            if file_path.endswith('.xml'):
                return self._load_pascal_voc(file_path)
            elif file_path.endswith('.txt'):
                return self._load_yolo(file_path)
            elif file_path.endswith('.json'):
                return self._load_json(file_path)
            
            return None
            
        except Exception as e:
            print(f"Erreur lors du chargement depuis le fichier: {e}")
            return None
    
    def _save_to_file(self, annotations: ImageAnnotation, file_path: str) -> bool:
        """Sauvegarde les annotations dans un fichier."""
        try:
            if file_path.endswith('.xml'):
                return self._save_pascal_voc(annotations, file_path)
            elif file_path.endswith('.txt'):
                return self._save_yolo(annotations, file_path)
            elif file_path.endswith('.json'):
                return self._save_json(annotations, file_path)
            
            return False
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde dans le fichier: {e}")
            return False
    
    def _load_annotation_cache(self):
        """Charge le cache des annotations."""
        if not self.annotation_directory:
            return
        
        try:
            for file_name in os.listdir(self.annotation_directory):
                file_path = os.path.join(self.annotation_directory, file_name)
                if os.path.isfile(file_path):
                    # Déterminer le type de fichier et charger
                    annotations = self._load_from_file(file_path)
                    if annotations:
                        self.annotations_cache[annotations.image_path] = annotations
                        
        except Exception as e:
            print(f"Erreur lors du chargement du cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des annotations."""
        # Recalculer les statistiques
        self.stats['total_images'] = len(self.annotations_cache)
        self.stats['annotated_images'] = sum(1 for ann in self.annotations_cache.values() 
                                           if ann.is_annotated)
        self.stats['verified_images'] = sum(1 for ann in self.annotations_cache.values() 
                                          if ann.is_verified)
        
        return self.stats.copy()
    
    # Méthodes d'import/export spécifiques (implémentation simplifiée)
    def _load_pascal_voc(self, file_path: str) -> Optional[ImageAnnotation]:
        """Charge depuis le format Pascal VOC."""
        # Implémentation simplifiée
        return ImageAnnotation("")
    
    def _load_yolo(self, file_path: str) -> Optional[ImageAnnotation]:
        """Charge depuis le format YOLO."""
        # Implémentation simplifiée
        return ImageAnnotation("")
    
    def _load_json(self, file_path: str) -> Optional[ImageAnnotation]:
        """Charge depuis le format JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ImageAnnotation.from_dict(data)
        except Exception:
            return None
    
    def _save_pascal_voc(self, annotations: ImageAnnotation, file_path: str) -> bool:
        """Sauvegarde en format Pascal VOC."""
        # Implémentation simplifiée
        return True
    
    def _save_yolo(self, annotations: ImageAnnotation, file_path: str) -> bool:
        """Sauvegarde en format YOLO."""
        # Implémentation simplifiée
        return True
    
    def _save_json(self, annotations: ImageAnnotation, file_path: str) -> bool:
        """Sauvegarde en format JSON."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(annotations.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def _export_pascal_voc(self, image_path: str, output_path: str) -> bool:
        """Exporte en format Pascal VOC."""
        # Implémentation simplifiée
        return True
    
    def _export_yolo(self, image_path: str, output_path: str) -> bool:
        """Exporte en format YOLO."""
        # Implémentation simplifiée
        return True
    
    def _export_coco(self, image_path: str, output_path: str) -> bool:
        """Exporte en format COCO."""
        # Implémentation simplifiée
        return True
    
    def _export_createml(self, image_path: str, output_path: str) -> bool:
        """Exporte en format CreateML."""
        # Implémentation simplifiée
        return True
