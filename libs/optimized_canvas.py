#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
from typing import List, Optional, Tuple
from collections import deque

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.shape import Shape
from libs.utils import distance


class OptimizedCanvas(QWidget):
    """
    Canvas optimisé avec double buffering, culling et gestion intelligente des événements.
    """
    
    # Signaux
    zoomRequest = pyqtSignal(int)
    lightRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, int)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)
    
    CREATE, EDIT = list(range(2))
    epsilon = 24.0
    
    def __init__(self, *args, **kwargs):
        super(OptimizedCanvas, self).__init__(*args, **kwargs)
        
        # État initial
        self.mode = self.EDIT
        self.shapes = []
        self.current = None
        self.selected_shape = None
        self.selected_shape_copy = None
        self.drawing_line_color = QColor(0, 0, 255)
        self.drawing_rect_color = QColor(0, 0, 255)
        
        # Objets de dessin
        self.line = Shape(line_color=self.drawing_line_color)
        self.prev_point = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.overlay_color = None
        
        # Images et pixmaps
        self.pixmap = QPixmap()
        self.original_pixmap = QPixmap()  # Image originale non transformée
        
        # Optimisations
        self.double_buffer = QPixmap()  # Buffer pour double buffering
        self.needs_repaint = True
        self.partial_repaint = False
        self.repaint_region = QRect()
        
        # Culling et visibilité
        self.visible_shapes = set()
        self.viewport_rect = QRect()
        self.culling_enabled = True
        
        # Gestion des événements
        self.mouse_pos = QPointF()
        self.last_mouse_pos = QPointF()
        self.mouse_pressed = False
        self.drag_threshold = 5  # Seuil pour détecter le drag
        
        # Historique pour undo/redo
        self.history = deque(maxlen=50)
        self.history_index = -1
        
        # Performance
        self.frame_count = 0
        self.last_fps_time = QTime.currentTime()
        self.fps = 0
        
        # Configuration
        self.setMinimumSize(1, 1)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        
        # Timer pour les animations et mises à jour
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._on_update_timer)
        self.update_timer.setSingleShot(True)
        
        # Variables pour le dessin
        self.h_shape = None
        self.h_vertex = None
        self.h_edge = None
        self.moving_shape = False
        self.hiding = False
        self.hide_background = False
        self._hide_background = False
        
        # Couleurs et styles
        self.line_color = QColor(0, 255, 0)
        self.fill_color = QColor(255, 0, 0, 128)
        self.select_line_color = QColor(255, 255, 255)
        self.select_fill_color = QColor(0, 128, 255, 155)
        
        # Polices et tailles
        self.label_font_size = 8
        self.vertex_select_radius = 8.0
        self.edge_select_radius = 12.0
        self.vertex_fill_color = QColor(0, 255, 0, 255)
        self.h_vertex_fill_color = QColor(255, 0, 0, 255)
        self.h_edge_fill_color = QColor(255, 0, 0, 255)
        
        # Painter optimisé
        self._painter = QPainter()
        
        # État de vérification
        self.verified = False
        
        # Mode de dessin
        self.draw_square = False
    
    def set_culling_enabled(self, enabled: bool):
        """Active/désactive le culling des shapes."""
        self.culling_enabled = enabled
        self._update_visible_shapes()
        self.update()
    
    def _update_visible_shapes(self):
        """Met à jour la liste des shapes visibles dans le viewport."""
        if not self.culling_enabled or not self.pixmap:
            self.visible_shapes = set(range(len(self.shapes)))
            return
        
        self.visible_shapes.clear()
        viewport = self.viewport_rect
        
        for i, shape in enumerate(self.shapes):
            if self._is_shape_visible(shape, viewport):
                self.visible_shapes.add(i)
    
    def _is_shape_visible(self, shape: Shape, viewport: QRect) -> bool:
        """Vérifie si une shape est visible dans le viewport."""
        if not shape.points:
            return False
        
        # Calculer le bounding box de la shape
        min_x = min(p.x() for p in shape.points)
        max_x = max(p.x() for p in shape.points)
        min_y = min(p.y() for p in shape.points)
        max_y = max(p.y() for p in shape.points)
        
        shape_rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        
        # Appliquer la transformation (scale et offset)
        shape_rect = shape_rect.adjusted(
            self.offset_to_center().x(),
            self.offset_to_center().y(),
            self.offset_to_center().x(),
            self.offset_to_center().y()
        )
        shape_rect = shape_rect.adjusted(
            -self.epsilon, -self.epsilon,
            self.epsilon, self.epsilon
        )
        
        return shape_rect.intersects(viewport)
    
    def _create_double_buffer(self, size: QSize) -> QPixmap:
        """Crée un buffer pour le double buffering."""
        if (self.double_buffer.size() != size or 
            self.double_buffer.devicePixelRatio() != self.devicePixelRatio()):
            self.double_buffer = QPixmap(size)
            self.double_buffer.setDevicePixelRatio(self.devicePixelRatio())
            self.needs_repaint = True
        return self.double_buffer
    
    def paintEvent(self, event):
        """Événement de peinture optimisé avec double buffering."""
        if not self.pixmap or self.pixmap.isNull():
            return super(OptimizedCanvas, self).paintEvent(event)
        
        # Créer le buffer si nécessaire
        buffer = self._create_double_buffer(self.size())
        
        # Peindre dans le buffer seulement si nécessaire
        if self.needs_repaint:
            self._paint_to_buffer(buffer, event.rect())
            self.needs_repaint = False
            self.partial_repaint = False
        
        # Copier le buffer vers l'écran
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, buffer)
        painter.end()
        
        # Mettre à jour les statistiques FPS
        self._update_fps()
    
    def _paint_to_buffer(self, buffer: QPixmap, rect: QRect):
        """Peint le contenu dans le buffer."""
        painter = QPainter(buffer)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Effacer le buffer
        painter.fillRect(buffer.rect(), QColor(240, 240, 240))
        
        # Appliquer les transformations
        painter.scale(self.scale, self.scale)
        painter.translate(self.offset_to_center())
        
        # Dessiner l'image de base
        self._draw_background(painter)
        
        # Dessiner les shapes visibles seulement
        self._draw_shapes(painter, rect)
        
        # Dessiner la shape en cours de création
        self._draw_current_shape(painter)
        
        # Dessiner les guides de dessin
        self._draw_drawing_guides(painter)
        
        painter.end()
    
    def _draw_background(self, painter: QPainter):
        """Dessine l'image de fond."""
        if self.pixmap.isNull():
            return
        
        # Appliquer l'overlay si nécessaire
        if self.overlay_color:
            temp = QPixmap(self.pixmap)
            overlay_painter = QPainter(temp)
            overlay_painter.setCompositionMode(QPainter.CompositionMode_Overlay)
            overlay_painter.fillRect(temp.rect(), self.overlay_color)
            overlay_painter.end()
            painter.drawPixmap(0, 0, temp)
        else:
            painter.drawPixmap(0, 0, self.pixmap)
    
    def _draw_shapes(self, painter: QPainter, rect: QRect):
        """Dessine les shapes visibles."""
        Shape.scale = self.scale
        Shape.label_font_size = self.label_font_size
        
        # Dessiner seulement les shapes visibles
        for i, shape in enumerate(self.shapes):
            if i not in self.visible_shapes:
                continue
            
            if (shape.selected or not self._hide_background) and self.isVisible(shape):
                shape.fill = shape.selected or shape == self.h_shape
                shape.paint(painter)
    
    def _draw_current_shape(self, painter: QPainter):
        """Dessine la shape en cours de création."""
        if self.current:
            self.current.paint(painter)
            self.line.paint(painter)
        
        if self.selected_shape_copy:
            self.selected_shape_copy.paint(painter)
    
    def _draw_drawing_guides(self, painter: QPainter):
        """Dessine les guides de dessin."""
        # Rectangle de sélection en cours de création
        if self.current is not None and len(self.line) == 2:
            left_top = self.line[0]
            right_bottom = self.line[1]
            rect_width = right_bottom.x() - left_top.x()
            rect_height = right_bottom.y() - left_top.y()
            
            painter.setPen(self.drawing_rect_color)
            brush = QBrush(Qt.BDiagPattern)
            painter.setBrush(brush)
            painter.drawRect(int(left_top.x()), int(left_top.y()), 
                           int(rect_width), int(rect_height))
        
        # Lignes de guidage
        if self.drawing() and not self.prev_point.isNull() and not self.out_of_pixmap(self.prev_point):
            painter.setPen(QColor(0, 0, 0))
            painter.drawLine(int(self.prev_point.x()), 0, 
                           int(self.prev_point.x()), int(self.pixmap.height()))
            painter.drawLine(0, int(self.prev_point.y()), 
                           int(self.pixmap.width()), int(self.prev_point.y()))
    
    def _update_fps(self):
        """Met à jour les statistiques FPS."""
        self.frame_count += 1
        current_time = QTime.currentTime()
        
        if self.last_fps_time.msecsTo(current_time) >= 1000:  # Toutes les secondes
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time
    
    def _on_update_timer(self):
        """Callback du timer de mise à jour."""
        self.update()
    
    def queue_update(self, region: QRect = None):
        """Met en file d'attente une mise à jour."""
        if region:
            self.partial_repaint = True
            self.repaint_region = region
        else:
            self.needs_repaint = True
        
        # Démarrer le timer pour batch les mises à jour
        self.update_timer.start(16)  # ~60 FPS
    
    def load_pixmap(self, pixmap):
        """Charge un pixmap et met à jour le cache."""
        self.original_pixmap = pixmap
        self.pixmap = pixmap
        self.needs_repaint = True
        self._update_visible_shapes()
        self.queue_update()
    
    def load_shapes(self, shapes):
        """Charge les shapes et met à jour la visibilité."""
        self.shapes = list(shapes)
        self._update_visible_shapes()
        self.needs_repaint = True
        self.queue_update()
    
    def add_shape(self, shape: Shape):
        """Ajoute une shape et met à jour la visibilité."""
        self.shapes.append(shape)
        self._update_visible_shapes()
        self.needs_repaint = True
        self.queue_update()
    
    def remove_shape(self, shape: Shape):
        """Supprime une shape et met à jour la visibilité."""
        if shape in self.shapes:
            self.shapes.remove(shape)
            self._update_visible_shapes()
            self.needs_repaint = True
            self.queue_update()
    
    def resizeEvent(self, event):
        """Gère le redimensionnement."""
        super().resizeEvent(event)
        self.viewport_rect = QRect(0, 0, self.width(), self.height())
        self._update_visible_shapes()
        self.needs_repaint = True
        self.queue_update()
    
    def wheelEvent(self, event):
        """Gère la molette de la souris pour le zoom."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoomRequest.emit(1)
        else:
            self.zoomRequest.emit(-1)
        event.accept()
    
    def mousePressEvent(self, event):
        """Gère les clics de souris optimisés."""
        self.mouse_pos = event.pos()
        self.last_mouse_pos = event.pos()
        self.mouse_pressed = True
        
        # Délégation à l'implémentation originale pour la logique métier
        super().mousePressEvent(event)
        
        # Marquer pour mise à jour
        self.queue_update()
    
    def mouseMoveEvent(self, event):
        """Gère les mouvements de souris optimisés."""
        self.mouse_pos = event.pos()
        
        # Vérifier si c'est un vrai mouvement (pas juste du bruit)
        if self.last_mouse_pos and distance(self.last_mouse_pos, self.mouse_pos) < 1:
            return
        
        self.last_mouse_pos = self.mouse_pos
        
        # Délégation à l'implémentation originale
        super().mouseMoveEvent(event)
        
        # Mise à jour partielle seulement
        self.queue_update(QRect(event.pos().x() - 50, event.pos().y() - 50, 100, 100))
    
    def mouseReleaseEvent(self, event):
        """Gère le relâchement de souris."""
        self.mouse_pressed = False
        
        # Délégation à l'implémentation originale
        super().mouseReleaseEvent(event)
        
        # Mise à jour complète
        self.needs_repaint = True
        self.queue_update()
    
    def keyPressEvent(self, event):
        """Gère les touches optimisées."""
        # Délégation à l'implémentation originale
        super().keyPressEvent(event)
        
        # Mise à jour si nécessaire
        self.queue_update()
    
    # Méthodes héritées de Canvas original (délégation)
    def drawing(self):
        """Retourne True si en mode dessin."""
        return self.mode == self.CREATE
    
    def set_drawing_mode(self, mode):
        """Définit le mode de dessin."""
        self.mode = mode
        self.queue_update()
    
    def finalise(self):
        """Finalise la shape en cours."""
        if self.current:
            self.current.close()
            self.shapes.append(self.current)
            self.current = None
            self.set_hiding(False)
            self.newShape.emit()
            self._update_visible_shapes()
            self.needs_repaint = True
            self.queue_update()
    
    def delete_selected(self):
        """Supprime la shape sélectionnée."""
        if self.selected_shape and self.selected_shape in self.shapes:
            shape = self.selected_shape
            self.shapes.remove(shape)
            self.selected_shape = None
            self._update_visible_shapes()
            self.needs_repaint = True
            self.queue_update()
            return shape
        return None
    
    def copy_selected_shape(self):
        """Copie la shape sélectionnée."""
        if self.selected_shape:
            self.selected_shape_copy = self.selected_shape.copy()
            self.needs_repaint = True
            self.queue_update()
    
    def set_shape_visible(self, shape, value):
        """Définit la visibilité d'une shape."""
        # Cette méthode devrait être implémentée selon les besoins
        self.queue_update()
    
    def isVisible(self, shape):
        """Vérifie si une shape est visible."""
        return True  # Simplification pour l'instant
    
    def set_hiding(self, enable=True):
        """Active/désactive le masquage."""
        self._hide_background = self.hide_background if enable else False
        self.queue_update()
    
    def offset_to_center(self):
        """Calcule l'offset pour centrer l'image."""
        s = self.scale
        area = super(OptimizedCanvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)
    
    def out_of_pixmap(self, p):
        """Vérifie si un point est hors du pixmap."""
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)
    
    def get_fps(self) -> int:
        """Retourne le FPS actuel."""
        return self.fps
    
    def get_visible_shapes_count(self) -> int:
        """Retourne le nombre de shapes visibles."""
        return len(self.visible_shapes)
    
    def get_total_shapes_count(self) -> int:
        """Retourne le nombre total de shapes."""
        return len(self.shapes)
