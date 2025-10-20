#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gestionnaire de projets - Gère l'ouverture, la sauvegarde et la fermeture des projets.
"""

import os
import json
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    from PyQt4.QtCore import QObject, pyqtSignal


class ProjectInfo:
    """Informations sur un projet."""
    
    def __init__(self, name: str = "", path: str = "", created: str = None):
        self.name = name
        self.path = path
        self.created = created or datetime.now().isoformat()
        self.modified = self.created
        self.description = ""
        self.version = "1.0"
        self.author = ""
        self.tags = []
        self.image_count = 0
        self.annotation_count = 0
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'name': self.name,
            'path': self.path,
            'created': self.created,
            'modified': self.modified,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'tags': self.tags,
            'image_count': self.image_count,
            'annotation_count': self.annotation_count,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectInfo':
        """Crée depuis un dictionnaire."""
        info = cls()
        for key, value in data.items():
            if hasattr(info, key):
                setattr(info, key, value)
        return info


class ProjectManager(QObject):
    """
    Gestionnaire de projets pour l'annotation d'images.
    """
    
    # Signaux
    projectOpened = pyqtSignal(str)  # project_path
    projectClosed = pyqtSignal()
    projectSaved = pyqtSignal(str)  # project_path
    projectCreated = pyqtSignal(str)  # project_path
    projectDeleted = pyqtSignal(str)  # project_path
    imageListChanged = pyqtSignal(list)  # List[str]
    annotationListChanged = pyqtSignal(list)  # List[str]
    
    def __init__(self):
        super().__init__()
        
        # État du projet actuel
        self.current_project: Optional[ProjectInfo] = None
        self.project_path: Optional[str] = None
        self.image_directory: Optional[str] = None
        self.annotation_directory: Optional[str] = None
        
        # Liste des fichiers
        self.image_files: List[str] = []
        self.annotation_files: List[str] = []
        
        # Configuration du projet
        self.project_config = {
            'supported_image_formats': ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff', '.webp'],
            'supported_annotation_formats': ['.xml', '.txt', '.json'],
            'default_annotation_format': '.xml',
            'auto_save': True,
            'backup_enabled': True,
            'backup_count': 5
        }
        
        # Historique des projets récents
        self.recent_projects: List[str] = []
        self.max_recent_projects = 10
        
        # État
        self.is_project_open = False
        self.is_dirty = False
    
    def create_project(self, project_path: str, project_name: str, 
                      image_directory: str, annotation_directory: str = None,
                      description: str = "") -> bool:
        """
        Crée un nouveau projet.
        
        Args:
            project_path: Chemin où créer le projet
            project_name: Nom du projet
            image_directory: Dossier contenant les images
            annotation_directory: Dossier pour les annotations (optionnel)
            description: Description du projet
            
        Returns:
            True si le projet est créé avec succès
        """
        try:
            # Créer le dossier du projet
            os.makedirs(project_path, exist_ok=True)
            
            # Créer les sous-dossiers
            if not annotation_directory:
                annotation_directory = os.path.join(project_path, "annotations")
            
            os.makedirs(annotation_directory, exist_ok=True)
            
            # Créer les fichiers de configuration
            self._create_project_files(project_path, project_name, image_directory, 
                                     annotation_directory, description)
            
            # Ouvrir le projet créé
            if self.open_project(project_path):
                self.projectCreated.emit(project_path)
                return True
            
            return False
            
        except Exception as e:
            print(f"Erreur lors de la création du projet: {e}")
            return False
    
    def _create_project_files(self, project_path: str, project_name: str,
                            image_directory: str, annotation_directory: str,
                            description: str):
        """Crée les fichiers de configuration du projet."""
        
        # Fichier de configuration principal
        project_info = ProjectInfo(
            name=project_name,
            path=project_path,
            created=datetime.now().isoformat()
        )
        project_info.description = description
        
        config_file = os.path.join(project_path, "project.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(project_info.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Fichier de configuration des paramètres
        settings = {
            'image_directory': image_directory,
            'annotation_directory': annotation_directory,
            'default_annotation_format': self.project_config['default_annotation_format'],
            'auto_save': self.project_config['auto_save'],
            'backup_enabled': self.project_config['backup_enabled'],
            'created': datetime.now().isoformat()
        }
        
        settings_file = os.path.join(project_path, "settings.json")
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        # Dossier pour les sauvegardes
        backup_dir = os.path.join(project_path, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Dossier pour les exports
        export_dir = os.path.join(project_path, "exports")
        os.makedirs(export_dir, exist_ok=True)
        
        # Fichier README
        readme_content = f"""# {project_name}

{description}

## Structure du projet

- `images/`: Dossier contenant les images à annoter
- `annotations/`: Dossier contenant les annotations
- `backups/`: Sauvegardes automatiques
- `exports/`: Exports de données

## Formats supportés

### Images
{', '.join(self.project_config['supported_image_formats'])}

### Annotations
{', '.join(self.project_config['supported_annotation_formats'])}

Créé le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        readme_file = os.path.join(project_path, "README.md")
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
    
    def open_project(self, project_path: str) -> bool:
        """
        Ouvre un projet existant.
        
        Args:
            project_path: Chemin vers le projet
            
        Returns:
            True si le projet est ouvert avec succès
        """
        try:
            # Vérifier que le projet existe
            if not os.path.exists(project_path):
                return False
            
            config_file = os.path.join(project_path, "project.json")
            if not os.path.exists(config_file):
                return False
            
            # Charger les informations du projet
            with open(config_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            self.current_project = ProjectInfo.from_dict(project_data)
            self.project_path = project_path
            
            # Charger les paramètres
            settings_file = os.path.join(project_path, "settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                self.image_directory = settings.get('image_directory', '')
                self.annotation_directory = settings.get('annotation_directory', '')
                self.project_config.update(settings)
            
            # Charger les listes de fichiers
            self._load_file_lists()
            
            # Ajouter aux projets récents
            self._add_to_recent_projects(project_path)
            
            self.is_project_open = True
            self.is_dirty = False
            
            self.projectOpened.emit(project_path)
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'ouverture du projet: {e}")
            return False
    
    def close_project(self):
        """Ferme le projet actuel."""
        if self.is_project_open:
            # Sauvegarder si nécessaire
            if self.is_dirty:
                self.save_project()
            
            # Réinitialiser l'état
            self.current_project = None
            self.project_path = None
            self.image_directory = None
            self.annotation_directory = None
            self.image_files.clear()
            self.annotation_files.clear()
            
            self.is_project_open = False
            self.is_dirty = False
            
            self.projectClosed.emit()
    
    def save_project(self) -> bool:
        """
        Sauvegarde le projet actuel.
        
        Returns:
            True si la sauvegarde réussit
        """
        if not self.is_project_open or not self.project_path:
            return False
        
        try:
            # Mettre à jour les informations du projet
            if self.current_project:
                self.current_project.modified = datetime.now().isoformat()
                self.current_project.image_count = len(self.image_files)
                self.current_project.annotation_count = len(self.annotation_files)
                
                # Sauvegarder le fichier de configuration
                config_file = os.path.join(self.project_path, "project.json")
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.current_project.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Sauvegarder les paramètres
            settings_file = os.path.join(self.project_path, "settings.json")
            settings = {
                'image_directory': self.image_directory,
                'annotation_directory': self.annotation_directory,
                'default_annotation_format': self.project_config['default_annotation_format'],
                'auto_save': self.project_config['auto_save'],
                'backup_enabled': self.project_config['backup_enabled'],
                'modified': datetime.now().isoformat()
            }
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            # Créer une sauvegarde si activée
            if self.project_config.get('backup_enabled', False):
                self._create_backup()
            
            self.is_dirty = False
            self.projectSaved.emit(self.project_path)
            return True
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du projet: {e}")
            return False
    
    def _create_backup(self):
        """Crée une sauvegarde du projet."""
        if not self.project_path:
            return
        
        try:
            backup_dir = os.path.join(self.project_path, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            
            # Créer une archive des fichiers de configuration
            config_files = ["project.json", "settings.json"]
            backup_files = []
            
            for file_name in config_files:
                file_path = os.path.join(self.project_path, file_name)
                if os.path.exists(file_path):
                    backup_files.append(file_path)
            
            if backup_files:
                backup_path = os.path.join(backup_dir, f"{backup_name}.json")
                backup_data = {
                    'timestamp': timestamp,
                    'files': {}
                }
                
                for file_path in backup_files:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        backup_data['files'][os.path.basename(file_path)] = json.load(f)
                
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
                # Nettoyer les anciennes sauvegardes
                self._cleanup_old_backups(backup_dir)
                
        except Exception as e:
            print(f"Erreur lors de la création de la sauvegarde: {e}")
    
    def _cleanup_old_backups(self, backup_dir: str):
        """Nettoie les anciennes sauvegardes."""
        try:
            backup_files = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.json')]
            backup_files.sort(reverse=True)  # Plus récent en premier
            
            max_backups = self.project_config.get('backup_count', 5)
            for old_backup in backup_files[max_backups:]:
                old_path = os.path.join(backup_dir, old_backup)
                os.remove(old_path)
                
        except Exception as e:
            print(f"Erreur lors du nettoyage des sauvegardes: {e}")
    
    def _load_file_lists(self):
        """Charge les listes de fichiers d'images et d'annotations."""
        self.image_files.clear()
        self.annotation_files.clear()
        
        # Charger les images
        if self.image_directory and os.path.exists(self.image_directory):
            for file_name in os.listdir(self.image_directory):
                file_path = os.path.join(self.image_directory, file_name)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_name.lower())
                    if ext in self.project_config['supported_image_formats']:
                        self.image_files.append(file_path)
        
        # Charger les annotations
        if self.annotation_directory and os.path.exists(self.annotation_directory):
            for file_name in os.listdir(self.annotation_directory):
                file_path = os.path.join(self.annotation_directory, file_name)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_name.lower())
                    if ext in self.project_config['supported_annotation_formats']:
                        self.annotation_files.append(file_path)
        
        # Trier les listes
        self.image_files.sort()
        self.annotation_files.sort()
        
        # Émettre les signaux
        self.imageListChanged.emit(self.image_files.copy())
        self.annotationListChanged.emit(self.annotation_files.copy())
    
    def _add_to_recent_projects(self, project_path: str):
        """Ajoute un projet à la liste des projets récents."""
        if project_path in self.recent_projects:
            self.recent_projects.remove(project_path)
        
        self.recent_projects.insert(0, project_path)
        
        # Limiter le nombre de projets récents
        if len(self.recent_projects) > self.max_recent_projects:
            self.recent_projects = self.recent_projects[:self.max_recent_projects]
    
    def get_image_paths(self) -> List[str]:
        """Retourne la liste des chemins d'images."""
        return self.image_files.copy()
    
    def get_annotation_paths(self) -> List[str]:
        """Retourne la liste des chemins d'annotations."""
        return self.annotation_files.copy()
    
    def get_annotation_directory(self) -> Optional[str]:
        """Retourne le répertoire des annotations."""
        return self.annotation_directory
    
    def get_image_directory(self) -> Optional[str]:
        """Retourne le répertoire des images."""
        return self.image_directory
    
    def get_project_info(self) -> Optional[ProjectInfo]:
        """Retourne les informations du projet actuel."""
        return self.current_project
    
    def get_recent_projects(self) -> List[str]:
        """Retourne la liste des projets récents."""
        return self.recent_projects.copy()
    
    def is_project_open(self) -> bool:
        """Vérifie si un projet est ouvert."""
        return self.is_project_open
    
    def is_dirty(self) -> bool:
        """Vérifie si le projet a des modifications non sauvegardées."""
        return self.is_dirty
    
    def mark_dirty(self):
        """Marque le projet comme modifié."""
        self.is_dirty = True
    
    def set_image_directory(self, directory: str):
        """Définit le répertoire des images."""
        if os.path.exists(directory):
            self.image_directory = directory
            self._load_file_lists()
            self.mark_dirty()
    
    def set_annotation_directory(self, directory: str):
        """Définit le répertoire des annotations."""
        if os.path.exists(directory):
            self.annotation_directory = directory
            self._load_file_lists()
            self.mark_dirty()
    
    def get_project_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du projet."""
        return {
            'is_open': self.is_project_open,
            'project_path': self.project_path,
            'image_count': len(self.image_files),
            'annotation_count': len(self.annotation_files),
            'is_dirty': self.is_dirty,
            'recent_projects_count': len(self.recent_projects),
            'image_directory': self.image_directory,
            'annotation_directory': self.annotation_directory
        }
