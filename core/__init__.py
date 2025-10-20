#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module core - Composants centraux de l'application.
"""

from .application import Application
from .project_manager import ProjectManager
from .annotation_manager import AnnotationManager
from .config_manager import ConfigManager

__all__ = [
    'Application',
    'ProjectManager', 
    'AnnotationManager',
    'ConfigManager'
]
