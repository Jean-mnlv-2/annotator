#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import json
import codecs
import os.path
import platform
import shutil
import sys
import time
import webbrowser as wb
from functools import partial

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError as e:
    raise ImportError(
        "PyQt5 introuvable. Assurez-vous d'utiliser le bon interpréteur et d'installer: "
        "pip install pyqt5 pyqt5-sip lxml"
    ) from e

from libs.combobox import ComboBox
from libs.default_label_combobox import DefaultLabelComboBox
from libs.resources import *
from libs.constants import *
from libs.utils import *
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.lightWidget import LightWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError, LabelFileFormat
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import YoloReader
from libs.yolo_io import TXT_EXT
from libs.create_ml_io import CreateMLReader
from libs.create_ml_io import JSON_EXT
from libs.coco_io import CocoReader
from libs.ustr import ustr
from libs.hashableQListWidgetItem import HashableQListWidgetItem
from libs.classManagerDialog import ClassManagerDialog
from libs.preferences_dialog import PreferencesDialog
from libs.shortcuts_dialog import ShortcutsDialog

__appname__ = 'AKOUMA Annotator'


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            add_actions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            add_actions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    # Async image loading signal (path, QImage)
    try:
        imageLoaded = pyqtSignal(str, QImage)
    except Exception:
        # PyQt4 compatibility fallback; signal will be connected on the thread object
        imageLoaded = None
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, default_filename=None, default_prefdef_class_file=None, default_save_dir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        # Enable drag & drop on main window
        try:
            self.setAcceptDrops(True)
        except Exception:
            pass

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        self.os_name = platform.system()

        # Load string bundle for i18n (use persisted locale if available)
        desired_locale = settings.get(SETTING_LOCALE, None)
        self.string_bundle = StringBundle.get_bundle(desired_locale)
        get_str = lambda str_id: self.string_bundle.get_string(str_id)

        # Save as Pascal voc xml
        self.default_save_dir = default_save_dir
        self.label_file_format = settings.get(SETTING_LABEL_FILE_FORMAT, LabelFileFormat.PASCAL_VOC)

        # For loading all image under a directory
        self.m_img_list = []
        self.dir_name = None
        self.label_hist = []
        self.last_open_dir = None
        self.cur_img_idx = 0
        self.img_count = len(self.m_img_list)

        # Whether we need to save or not.
        self.dirty = False

        self._no_selection_slot = False
        self._beginner = True
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.load_predefined_classes(default_prefdef_class_file)

        if self.label_hist:
            self.default_label = self.label_hist[0]
        else:
            print("Not find:/data/predefined_classes.txt (optional)")

        # Main widgets and related state.
        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)

        self.items_to_shapes = {}
        self.shapes_to_items = {}
        self.prev_label_text = ''

        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label
        self.use_default_label_checkbox = QCheckBox(get_str('useDefaultLabel'))
        self.use_default_label_checkbox.setChecked(False)
        self.default_label_combo_box = DefaultLabelComboBox(self,items=self.label_hist)

        use_default_label_qhbox_layout = QHBoxLayout()
        use_default_label_qhbox_layout.addWidget(self.use_default_label_checkbox)
        use_default_label_qhbox_layout.addWidget(self.default_label_combo_box)
        use_default_label_container = QWidget()
        use_default_label_container.setLayout(use_default_label_qhbox_layout)

        # Create a widget for edit and diffc button
        self.diffc_button = QCheckBox(get_str('useDifficult'))
        self.diffc_button.setChecked(False)
        self.diffc_button.stateChanged.connect(self.button_state)
        self.edit_button = QToolButton()
        self.edit_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Add some of widgets to list_layout
        list_layout.addWidget(self.edit_button)
        list_layout.addWidget(self.diffc_button)
        list_layout.addWidget(use_default_label_container)

        # Create and add combobox for showing unique labels in group
        self.combo_box = ComboBox(self)
        list_layout.addWidget(self.combo_box)

        # Create and add a widget for showing current label items
        self.label_list = QListWidget()
        label_list_container = QWidget()
        label_list_container.setLayout(list_layout)
        self.label_list.itemActivated.connect(self.label_selection_changed)
        self.label_list.itemSelectionChanged.connect(self.label_selection_changed)
        self.label_list.itemDoubleClicked.connect(self.edit_label)
        # Connect to itemChanged to detect checkbox changes.
        self.label_list.itemChanged.connect(self.label_item_changed)
        list_layout.addWidget(self.label_list)



        self.dock = QDockWidget(get_str('boxLabelText'), self)
        self.dock.setObjectName(get_str('labels'))
        self.dock.setWidget(label_list_container)

        self.file_list_widget = QListWidget()
        self.file_list_widget.itemDoubleClicked.connect(self.file_item_double_clicked)
        file_list_layout = QVBoxLayout()
        file_list_layout.setContentsMargins(0, 0, 0, 0)
        # Quick search bar for file list
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText('Rechercher des fichiers...')
        self.file_search.textChanged.connect(self._filter_files)
        file_list_layout.addWidget(self.file_search)
        file_list_layout.addWidget(self.file_list_widget)
        # thumbnails in file list
        self.file_list_widget.setIconSize(QSize(64, 64))
        self.file_list_widget.setUniformItemSizes(True)
        file_list_container = QWidget()
        file_list_container.setLayout(file_list_layout)
        self.file_dock = QDockWidget(get_str('fileList'), self)
        self.file_dock.setObjectName(get_str('files'))
        self.file_dock.setWidget(file_list_container)

        self.zoom_widget = ZoomWidget()
        self.light_widget = LightWidget(get_str('lightWidgetTitle'))
        self.color_dialog = ColorDialog(parent=self)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoom_request)
        self.canvas.lightRequest.connect(self.light_request)
        self.canvas.set_drawing_shape_to_square(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scroll_area = scroll
        self.canvas.scrollRequest.connect(self.scroll_request)

        self.canvas.newShape.connect(self.new_shape)
        self.canvas.shapeMoved.connect(self.on_shape_moved)
        self.canvas.selectionChanged.connect(self.shape_selection_changed)
        self.canvas.drawingPolygon.connect(self.toggle_drawing_sensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFloatable)

        # Annotation Preview dock (right side)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText('Preview des annotations selon le format sélectionné...')
        self.preview_dock = QDockWidget('Annotation Preview', self)
        self.preview_dock.setObjectName('preview')
        self.preview_dock.setWidget(self.preview_text)
        self.addDockWidget(Qt.RightDockWidgetArea, self.preview_dock)

        self.dock_features = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dock_features)

        # Actions
        action = partial(new_action, self)
        quit = action(get_str('quit'), self.close,
                      'Ctrl+Q', 'quit', get_str('quitApp'))

        open = action(get_str('openFile'), self.open_file,
                      'Ctrl+O', 'open', get_str('openFileDetail'))

        open_dir = action(get_str('openDir'), self.open_dir_dialog,
                          'Ctrl+u', 'open', get_str('openDir'))

        change_save_dir = action(get_str('changeSaveDir'), self.change_save_dir_dialog,
                                 'Ctrl+r', 'open', get_str('changeSavedAnnotationDir'))

        manage_classes = action('Manage Classes', self.open_class_manager,
                                 None, 'labels', 'Edit class list')

        export_shortcuts = action('Export Shortcuts…', self.export_shortcuts,
                                  None, 'save', 'Export keyboard shortcuts to JSON')
        import_shortcuts = action('Import Shortcuts…', self.import_shortcuts,
                                  None, 'open', 'Import keyboard shortcuts from JSON')

        batch_rename = action('Renommer les images…', self.batch_rename_images,
                               None, 'edit', 'Renommer toutes les images du dossier courant avec un préfixe et un compteur')

        open_annotation = action(get_str('openAnnotation'), self.open_annotation_dialog,
                                 'Ctrl+Shift+O', 'open', get_str('openAnnotationDetail'))
        copy_prev_bounding = action(get_str('copyPrevBounding'), self.copy_previous_bounding_boxes, 'Ctrl+v', 'copy', get_str('copyPrevBounding'))

        open_next_image = action(get_str('nextImg'), self.open_next_image,
                                 'd', 'next', get_str('nextImgDetail'))

        open_prev_image = action(get_str('prevImg'), self.open_prev_image,
                                 'a', 'prev', get_str('prevImgDetail'))

        verify = action(get_str('verifyImg'), self.verify_image,
                        'space', 'verify', get_str('verifyImgDetail'))

        save = action(get_str('save'), self.save_file,
                      'Ctrl+S', 'save', get_str('saveDetail'), enabled=False)

        def get_format_meta(format):
            """
            returns a tuple containing (title, icon_name) of the selected format
            """
            if format == LabelFileFormat.PASCAL_VOC:
                return '&PascalVOC', 'format_voc'
            elif format == LabelFileFormat.YOLO:
                return '&YOLO', 'format_yolo'
            elif format == LabelFileFormat.CREATE_ML:
                return '&CreateML', 'format_createml'
            elif format == LabelFileFormat.COCO:
                return '&COCO', 'format_voc'

        save_format = action(get_format_meta(self.label_file_format)[0],
                             self.change_format, 'Ctrl+Y',
                             get_format_meta(self.label_file_format)[1],
                             get_str('changeSaveFormat'), enabled=True)

        save_as = action(get_str('saveAs'), self.save_file_as,
                         'Ctrl+Shift+S', 'save-as', get_str('saveAsDetail'), enabled=False)

        close = action(get_str('closeCur'), self.close_file, 'Ctrl+W', 'close', get_str('closeCurDetail'))

        delete_image = action(get_str('deleteImg'), self.delete_image, 'Ctrl+Shift+D', 'close', get_str('deleteImgDetail'))

        reset_all = action(get_str('resetAll'), self.reset_all, None, 'resetall', get_str('resetAllDetail'))

        color1 = action(get_str('boxLineColor'), self.choose_color1,
                        'Ctrl+L', 'color_line', get_str('boxLineColorDetail'))

        create_mode = action(get_str('crtBox'), self.set_create_mode,
                             'w', 'new', get_str('crtBoxDetail'), enabled=False)
        edit_mode = action(get_str('editBox'), self.set_edit_mode,
                           'Ctrl+J', 'edit', get_str('editBoxDetail'), enabled=False)

        create = action(get_str('crtBox'), self.create_shape,
                        'w', 'new', get_str('crtBoxDetail'), enabled=False)
        delete = action(get_str('delBox'), self.delete_selected_shape,
                        'Delete', 'delete', get_str('delBoxDetail'), enabled=False)
        copy = action(get_str('dupBox'), self.copy_selected_shape,
                      'Ctrl+D', 'copy', get_str('dupBoxDetail'),
                      enabled=False)

        undo_act = action('Undo', self.undo_action, 'Ctrl+Z', 'undo', 'Undo last action', enabled=False)
        redo_act = action('Redo', self.redo_action, 'Ctrl+Shift+Z', 'undo', 'Redo last undone action', enabled=False)

        advanced_mode = action(get_str('advancedMode'), self.toggle_advanced_mode,
                               'Ctrl+Shift+A', 'expert', get_str('advancedModeDetail'),
                               checkable=True)

        # Dark mode toggle
        dark_mode = action('Dark Mode', self.toggle_dark_mode,
                           'Ctrl+Shift+D', 'expert', 'Toggle dark theme', checkable=True)
        # Persisted dark mode state
        dark_enabled = settings.get(SETTING_DARK_MODE, False)
        dark_mode.setChecked(dark_enabled)
        if dark_enabled:
            self.toggle_dark_mode(True)
        # keep reference for persistence in closeEvent
        self._dark_mode_action = dark_mode

        hide_all = action(get_str('hideAllBox'), partial(self.toggle_polygons, False),
                          'Ctrl+H', 'hide', get_str('hideAllBoxDetail'),
                          enabled=False)
        show_all = action(get_str('showAllBox'), partial(self.toggle_polygons, True),
                          'Ctrl+A', 'hide', get_str('showAllBoxDetail'),
                          enabled=False)

        help_default = action(get_str('tutorialDefault'), self.show_default_tutorial_dialog, None, 'help', get_str('tutorialDetail'))
        show_info = action(get_str('info'), self.show_info_dialog, None, 'help', get_str('info'))
        show_shortcut = action(get_str('shortcut'), self.show_shortcuts_dialog, None, 'help', get_str('shortcut'))

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoom_widget)
        self.zoom_widget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (format_shortcut("Ctrl+[-+]"),
                                             format_shortcut("Ctrl+Wheel")))
        self.zoom_widget.setEnabled(False)

        zoom_in = action(get_str('zoomin'), partial(self.add_zoom, 10),
                         'Ctrl++', 'zoom-in', get_str('zoominDetail'), enabled=False)
        zoom_out = action(get_str('zoomout'), partial(self.add_zoom, -10),
                          'Ctrl+-', 'zoom-out', get_str('zoomoutDetail'), enabled=False)
        zoom_org = action(get_str('originalsize'), partial(self.set_zoom, 100),
                          'Ctrl+=', 'zoom', get_str('originalsizeDetail'), enabled=False)
        fit_window = action(get_str('fitWin'), self.set_fit_window,
                            'Ctrl+F', 'fit-window', get_str('fitWinDetail'),
                            checkable=True, enabled=False)
        fit_width = action(get_str('fitWidth'), self.set_fit_width,
                           'Ctrl+Shift+F', 'fit-width', get_str('fitWidthDetail'),
                           checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoom_actions = (self.zoom_widget, zoom_in, zoom_out,
                        zoom_org, fit_window, fit_width)
        self.zoom_mode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        light = QWidgetAction(self)
        light.setDefaultWidget(self.light_widget)
        self.light_widget.setWhatsThis(
            u"Brighten or darken current image. Also accessible with"
            " %s and %s from the canvas." % (format_shortcut("Ctrl+Shift+[-+]"),
                                             format_shortcut("Ctrl+Shift+Wheel")))
        self.light_widget.setEnabled(False)

        light_brighten = action(get_str('lightbrighten'), partial(self.add_light, 10),
                                'Ctrl+Shift++', 'light_lighten', get_str('lightbrightenDetail'), enabled=False)
        light_darken = action(get_str('lightdarken'), partial(self.add_light, -10),
                              'Ctrl+Shift+-', 'light_darken', get_str('lightdarkenDetail'), enabled=False)
        light_org = action(get_str('lightreset'), partial(self.set_light, 50),
                           'Ctrl+Shift+=', 'light_reset', get_str('lightresetDetail'), checkable=True, enabled=False)
        light_org.setChecked(True)

        # Group light controls into a list for easier toggling.
        light_actions = (self.light_widget, light_brighten,
                         light_darken, light_org)

        edit = action(get_str('editLabel'), self.edit_label,
                      'Ctrl+E', 'edit', get_str('editLabelDetail'),
                      enabled=False)
        self.edit_button.setDefaultAction(edit)

        shape_line_color = action(get_str('shapeLineColor'), self.choose_shape_line_color,
                                  icon='color_line', tip=get_str('shapeLineColorDetail'),
                                  enabled=False)
        shape_fill_color = action(get_str('shapeFillColor'), self.choose_shape_fill_color,
                                  icon='color', tip=get_str('shapeFillColorDetail'),
                                  enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText(get_str('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Label list context menu.
        label_menu = QMenu()
        add_actions(label_menu, (edit, delete))
        self.label_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label_list.customContextMenuRequested.connect(
            self.pop_label_list_menu)

        # Draw squares/rectangles
        self.draw_squares_option = QAction(get_str('drawSquares'), self)
        self.draw_squares_option.setShortcut('Ctrl+Shift+R')
        self.draw_squares_option.setCheckable(True)
        self.draw_squares_option.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.draw_squares_option.triggered.connect(self.toggle_draw_square)

        # Store actions for further handling.
        self.actions = Struct(save=save, save_format=save_format, saveAs=save_as, open=open, close=close, resetAll=reset_all, deleteImg=delete_image,
                              lineColor=color1, create=create, delete=delete, edit=edit, copy=copy,
                              createMode=create_mode, editMode=edit_mode, advancedMode=advanced_mode,
                              shapeLineColor=shape_line_color, shapeFillColor=shape_fill_color,
                              zoom=zoom, zoomIn=zoom_in, zoomOut=zoom_out, zoomOrg=zoom_org,
                              fitWindow=fit_window, fitWidth=fit_width,
                              zoomActions=zoom_actions,
                              lightBrighten=light_brighten, lightDarken=light_darken, lightOrg=light_org,
                              lightActions=light_actions,
                              fileMenuActions=(
                                  open, open_dir, save, save_as, close, reset_all, quit),
                              beginner=(), advanced=(),
                              editMenu=(edit, copy, delete,
                                        None, color1, self.draw_squares_option),
                              beginnerContext=(create, edit, copy, delete),
                              advancedContext=(create_mode, edit_mode, edit, copy,
                                               delete, shape_line_color, shape_fill_color),
                              onLoadActive=(
                                  close, create, create_mode, edit_mode),
                              onShapesPresent=(save_as, hide_all, show_all))

        self.menus = Struct(
            file=self.menu(get_str('menu_file')),
            edit=self.menu(get_str('menu_edit')),
            view=self.menu(get_str('menu_view')),
            help=self.menu(get_str('menu_help')),
            recentFiles=QMenu(get_str('menu_openRecent')),
            labelList=label_menu)

        # Simple filters menu under View
        self.filter_menu = QMenu('Filters', self)
        # dynamic class list will be populated later as labels change
        self.filter_menu.addAction('Unverified', lambda: self.apply_filter_menu('unverified'))
        self.filter_menu.addAction('Missing labels', lambda: self.apply_filter_menu('missing'))
        self.filter_menu.addSeparator()
        self.filter_menu.addAction('Show only current class', lambda: self._filter_show_current_class())
        self.filter_menu.addAction('Show all', lambda: self.toggle_polygons(True))

        # File list sorting controls
        self.sort_menu = QMenu('Sort files', self)
        self.sort_menu.addAction('Name A→Z', lambda: self._sort_file_list(alpha=True, reverse=False))
        self.sort_menu.addAction('Name Z→A', lambda: self._sort_file_list(alpha=True, reverse=True))
        self.sort_menu.addAction('Path depth', lambda: self._sort_file_list(depth=True))

        # Auto saving : Enable auto saving if pressing next
        self.auto_saving = QAction(get_str('autoSaveMode'), self)
        self.auto_saving.setCheckable(True)
        self.auto_saving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        # Auto-save interval (ms)
        self._autosave_interval_ms = settings.get('autosave/interval', 0) or 0
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(False)
        def _autosave_tick():
            if self.dirty and self.file_path:
                try:
                    self.save_file()
                except Exception:
                    pass
        self._autosave_timer.timeout.connect(_autosave_tick)
        def _toggle_autosave():
            if self.auto_saving.isChecked() and self._autosave_interval_ms > 0:
                self._autosave_timer.start(self._autosave_interval_ms)
            else:
                self._autosave_timer.stop()
        self.auto_saving.toggled.connect(_toggle_autosave)

        # Menu to set autosave interval
        self.autosave_menu = QMenu('Auto-save interval', self)
        def _set_interval(ms):
            self._autosave_interval_ms = ms
            self.settings['autosave/interval'] = ms
            self.settings.save()
            if self.auto_saving.isChecked() and ms > 0:
                self._autosave_timer.start(ms)
            else:
                self._autosave_timer.stop()
        self.autosave_menu.addAction('Off', lambda: _set_interval(0))
        self.autosave_menu.addAction('5s', lambda: _set_interval(5000))
        self.autosave_menu.addAction('15s', lambda: _set_interval(15000))
        self.autosave_menu.addAction('60s', lambda: _set_interval(60000))
        # Sync single class mode from PR#106
        self.single_class_mode = QAction(get_str('singleClsMode'), self)
        self.single_class_mode.setShortcut("Ctrl+Shift+S")
        self.single_class_mode.setCheckable(True)
        self.single_class_mode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.display_label_option = QAction(get_str('displayLabel'), self)
        self.display_label_option.setShortcut("Ctrl+Shift+P")
        self.display_label_option.setCheckable(True)
        self.display_label_option.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.display_label_option.triggered.connect(self.toggle_paint_labels_option)

        add_actions(self.menus.file,
                    (open, open_dir, change_save_dir, batch_rename, manage_classes, export_shortcuts, import_shortcuts, open_annotation, copy_prev_bounding, self.menus.recentFiles, save, save_format, save_as, close, reset_all, delete_image, quit))
        add_actions(self.menus.help, (help_default, show_info, show_shortcut))
        # Language submenu (FR/EN)
        self.language_menu = QMenu('Language', self)
        self._current_locale = settings.get(SETTING_LOCALE, None)
        def _switch_lang(locale_code):
            self._current_locale = locale_code
            QMessageBox.information(self, 'Language', 'La langue sera appliquée au redémarrage.')

        self.language_menu.addAction('Français', lambda: _switch_lang('fr'))
        self.language_menu.addAction('English', lambda: _switch_lang('en'))

        add_actions(self.menus.view, (
            self.auto_saving,
            self.autosave_menu,
            self.single_class_mode,
            self.display_label_option,
            dark_mode,
            self.language_menu,
            self.filter_menu,
            self.sort_menu,
            labels, advanced_mode, None,
            hide_all, show_all, None,
            zoom_in, zoom_out, zoom_org, None,
            fit_window, fit_width, None,
            light_brighten, light_darken, light_org))

        add_actions(self.menus.edit, (undo_act, redo_act, None))

        self.actions.undo = undo_act
        self.actions.redo = redo_act

        # Toggle Command Palette with Ctrl+P
        toggle_palette = action('Command Palette', self.toggle_command_palette, 'Ctrl+P', 'help', 'Open command palette')
        add_actions(self.menus.help, (toggle_palette,))

        # Preferences & Shortcuts editor entries
        try:
            prefs_act = action('Préférences…', self.open_preferences_dialog, 'Ctrl+,', 'settings', 'Ouvrir les préférences')
            shortcuts_editor_act = action('Éditeur de raccourcis…', self.open_shortcuts_editor, None, 'help', 'Modifier les raccourcis')
            add_actions(self.menus.edit, (prefs_act, shortcuts_editor_act,))
        except Exception:
            pass

        self.menus.file.aboutToShow.connect(self.update_file_menu)

        # Custom context menu for the canvas widget:
        add_actions(self.canvas.menus[0], self.actions.beginnerContext)
        add_actions(self.canvas.menus[1], (
            action('&Copy here', self.copy_shape),
            action('&Move here', self.move_shape)))

        # Shortcuts dock
        shortcuts_text = QPlainTextEdit()
        shortcuts_text.setReadOnly(True)
        shortcuts_text.setPlainText('''
Ctrl+O  Open File\nCtrl+U  Open Dir\nCtrl+R  Change Save Dir\nCtrl+S  Save\nW       Create Rect\nA/D     Prev/Next Image\nDel     Delete Box\nSpace   Verify Image\nCtrl++  Zoom In\nCtrl+-  Zoom Out
''')
        self.shortcuts_dock = QDockWidget('Shortcuts', self)
        try:
            # Remplir dynamiquement depuis ShortcutManager si disponible
            from libs.shortcut_manager import get_shortcut_manager
            sm = get_shortcut_manager()
            lines = []
            for act in sm.get_all_actions():
                if getattr(act, 'enabled', True):
                    lines.append(f"{act.current_key or act.default_key:8s}  {act.name}")
            shortcuts_text.setPlainText("\n".join(lines) if lines else shortcuts_text.toPlainText())
        except Exception:
            pass
        self.shortcuts_dock.setWidget(shortcuts_text)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.shortcuts_dock)
        # Style the left shortcuts dock with a green theme
        try:
            self.shortcuts_dock.setObjectName('ShortcutsDock')
            self.shortcuts_dock.setStyleSheet(
                "QDockWidget#ShortcutsDock::title {"
                "  background: #198754;"  # Bootstrap green
                "  color: #ffffff;"
                "  padding-left: 6px;"
                "  padding-top: 2px;"
                "  padding-bottom: 2px;"
                "}"
                "QDockWidget#ShortcutsDock {"
                "  background: #d1e7dd;"  # light green background
                "  border: 0;"
                "}"
            )
        except Exception:
            pass

        # Command Palette (minimal)
        self.command_palette = QLineEdit(self)
        self.command_palette.setPlaceholderText('Type to search commands... (Press Enter)')
        self.command_palette.returnPressed.connect(self._exec_command_palette)
        self.command_palette.hide()
        self.command_palette_dock = None

        self.tools = self.toolbar('Tools')
        # Green-themed left toolbar design
        try:
            self.tools.setIconSize(QSize(28, 28))
            self.tools.setStyleSheet(
                "QToolBar#ToolsToolBar {"
                "  background: #198754;"
                "  border: none;"
                "  padding: 6px;"
                "  spacing: 8px;"
                "}"
                "QToolBar#ToolsToolBar QToolButton {"
                "  color: #ffffff;"
                "}"
                "QToolBar#ToolsToolBar QToolButton:hover {"
                "  background: rgba(255,255,255,0.10);"
                "  border-radius: 4px;"
                "}"
            )
        except Exception:
            pass
        self.actions.beginner = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, verify, save, save_format, None, create, copy, delete, None,
            zoom_in, zoom, zoom_out, fit_window, fit_width, None,
            light_brighten, light, light_darken, light_org)

        self.actions.advanced = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, save, save_format, None,
            create_mode, edit_mode, None,
            hide_all, show_all)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Onboarding (first launch)
        if not settings.get(SETTING_ONBOARDING_SHOWN, False):
            QMessageBox.information(self, 'Bienvenue / Welcome',
                                    'Astuce: Utilisez Ctrl+U pour ouvrir un dossier, W pour créer une boîte, E pour éditer un label.\nShortcuts: Ctrl+S pour sauvegarder, A/D pour image précédente/suivante.\nVous pouvez changer la langue dans View > Language.')
            settings[SETTING_ONBOARDING_SHOWN] = True
            settings.save()

        # Application state.
        self.image = QImage()
        self.file_path = ustr(default_filename)
        self.last_open_dir = None
        self.recent_files = []
        self.max_recent = 7
        # Background image loader handle
        self._image_loader = None
        self._loading_path = None
        self.line_color = None
        self.fill_color = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)
                self.recent_files = [ustr(i) for i in recent_file_qstring_list]
            else:
                self.recent_files = recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        save_dir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.last_open_dir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.default_save_dir is None and save_dir is not None and os.path.exists(save_dir):
            self.default_save_dir = save_dir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.default_save_dir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.line_color = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fill_color = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.set_drawing_color(self.line_color)
        # Add chris
        Shape.difficult = self.difficult

        # simple thumbnail cache and preloader
        self._thumb_cache = {}
        self._next_image_cache = None

        # Undo/Redo history (snapshots of shapes)
        self._history = []
        self._redo = []
        self._history_debounce = False
        # Recently used labels (for numeric shortcuts 1-9)
        self._recent_labels = []

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggle_advanced_mode()

        # Populate the File menu dynamically.
        self.update_file_menu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.file_path and os.path.isdir(self.file_path):
            self.queue_event(partial(self.import_dir_images, self.file_path or ""))
        elif self.file_path:
            self.queue_event(partial(self.load_file, self.file_path or ""))

        # Callbacks:
        self.zoom_widget.valueChanged.connect(self.paint_canvas)
        self.light_widget.valueChanged.connect(self.paint_canvas)

        self.populate_mode_actions()

        # Display cursor coordinates at the right of status bar
        self.label_coordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.label_coordinates)

        # Open Dir if default file
        if self.file_path and os.path.isdir(self.file_path):
            self.open_dir_dialog(dir_path=self.file_path, silent=True)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.set_drawing_shape_to_square(False)
        if event.key() == Qt.Key_Escape and self.command_palette.isVisible():
            self.command_palette.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.set_drawing_shape_to_square(True)
        if event.key() == Qt.Key_P and (event.modifiers() & Qt.ControlModifier):
            self.toggle_command_palette()
        # Numeric shortcuts 1-9 to apply recent labels
        if Qt.Key_1 <= event.key() <= Qt.Key_9:
            idx = event.key() - Qt.Key_1
            if 0 <= idx < len(self._recent_labels):
                label_text = self._recent_labels[idx]
                # apply label to selected shape or start new shape with default
                if self.canvas.selected_shape is not None and self.canvas.editing():
                    item = self.shapes_to_items.get(self.canvas.selected_shape)
                    if item is not None:
                        item.setText(label_text)
                        item.setBackground(generate_color_by_text(label_text))
                        self.label_item_changed(item)
                else:
                    # set default label and trigger create
                    self.prev_label_text = label_text
                    self.create_shape()

    # Support Functions #
    def set_format(self, save_format):
        if save_format == FORMAT_PASCALVOC:
            self.actions.save_format.setText(FORMAT_PASCALVOC)
            self.actions.save_format.setIcon(new_icon("format_voc"))
            self.label_file_format = LabelFileFormat.PASCAL_VOC
            LabelFile.suffix = XML_EXT

        elif save_format == FORMAT_YOLO:
            self.actions.save_format.setText(FORMAT_YOLO)
            self.actions.save_format.setIcon(new_icon("format_yolo"))
            self.label_file_format = LabelFileFormat.YOLO
            LabelFile.suffix = TXT_EXT

        elif save_format == FORMAT_CREATEML:
            self.actions.save_format.setText(FORMAT_CREATEML)
            self.actions.save_format.setIcon(new_icon("format_createml"))
            self.label_file_format = LabelFileFormat.CREATE_ML
            LabelFile.suffix = JSON_EXT

        elif save_format == FORMAT_COCO:
            self.actions.save_format.setText(FORMAT_COCO)
            self.actions.save_format.setIcon(new_icon("format_voc"))
            self.label_file_format = LabelFileFormat.COCO
            LabelFile.suffix = JSON_EXT

    def change_format(self):
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            self.set_format(FORMAT_YOLO)
        elif self.label_file_format == LabelFileFormat.YOLO:
            self.set_format(FORMAT_CREATEML)
        elif self.label_file_format == LabelFileFormat.CREATE_ML:
            self.set_format(FORMAT_COCO)
        elif self.label_file_format == LabelFileFormat.COCO:
            self.set_format(FORMAT_PASCALVOC)
        else:
            raise ValueError('Unknown label file format.')
        self.set_dirty()
        self.update_annotation_preview()

    def no_shapes(self):
        return not self.items_to_shapes

    def toggle_advanced_mode(self, value=True):
        self._beginner = not value
        self.canvas.set_editing(True)
        self.populate_mode_actions()
        self.edit_button.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dock_features)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dock_features)

    def populate_mode_actions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        add_actions(self.tools, tool)
        self.canvas.menus[0].clear()
        add_actions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.create,) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        add_actions(self.menus.edit, actions + self.actions.editMenu)

    def set_beginner(self):
        self.tools.clear()
        add_actions(self.tools, self.actions.beginner)

    def set_advanced(self):
        self.tools.clear()
        add_actions(self.tools, self.actions.advanced)

    def set_dirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)
        self._push_history_snapshot()
        self.update_annotation_preview()

    def set_clean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)
        self.update_annotation_preview()

    def toggle_actions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for z in self.actions.lightActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queue_event(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def reset_state(self):
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()
        self.label_list.clear()
        self.file_path = None
        self.image_data = None
        self.label_file = None
        self.canvas.reset_state()
        self.label_coordinates.clear()
        self.combo_box.cb.clear()

    def current_item(self):
        items = self.label_list.selectedItems()
        if items:
            return items[0]
        return None

    def add_recent_file(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        elif len(self.recent_files) >= self.max_recent:
            self.recent_files.pop()
        self.recent_files.insert(0, file_path)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def show_tutorial_dialog(self, browser='default', link=None):
        if link is None:
            link = self.screencast

        if browser.lower() == 'default':
            wb.open(link, new=2)
        elif browser.lower() == 'chrome' and self.os_name == 'Windows':
            if shutil.which(browser.lower()):  # 'chrome' not in wb._browsers in windows
                wb.register('chrome', None, wb.BackgroundBrowser('chrome'))
            else:
                chrome_path="D:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
                if os.path.isfile(chrome_path):
                    wb.register('chrome', None, wb.BackgroundBrowser(chrome_path))
            try:
                wb.get('chrome').open(link, new=2)
            except:
                wb.open(link, new=2)
        elif browser.lower() in wb._browsers:
            wb.get(browser.lower()).open(link, new=2)

    def show_default_tutorial_dialog(self):
        self.show_tutorial_dialog(browser='default')

    def show_info_dialog(self):
        from libs.__init__ import __version__
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def show_shortcuts_dialog(self):
        self.show_tutorial_dialog(browser='default', link='https://github.com/tzutalin/labelImg#Hotkeys')

    def create_shape(self):
        assert self.beginner()
        self.canvas.set_editing(False)
        self.actions.create.setEnabled(False)

    def toggle_drawing_sensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print('Cancel creation.')
            self.canvas.set_editing(True)
            self.canvas.restore_cursor()
            self.actions.create.setEnabled(True)

    def toggle_draw_mode(self, edit=True):
        self.canvas.set_editing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def set_create_mode(self):
        assert self.advanced()
        self.toggle_draw_mode(False)

    def set_edit_mode(self):
        assert self.advanced()
        self.toggle_draw_mode(True)
        self.label_selection_changed()

    def update_file_menu(self):
        curr_file_path = self.file_path

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recent_files if f !=
                 curr_file_path and exists(f)]
        for i, f in enumerate(files):
            icon = new_icon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.load_recent, f))
            menu.addAction(action)

    def pop_label_list_menu(self, point):
        self.menus.labelList.exec_(self.label_list.mapToGlobal(point))

    def edit_label(self):
        if not self.canvas.editing():
            return
        item = self.current_item()
        if not item:
            return
        text = self.label_dialog.pop_up(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generate_color_by_text(text))
            self.set_dirty()
            self.update_combo_box()

    # Tzutalin 20160906 : Add file list and dock to move faster
    def file_item_double_clicked(self, item=None):
        self.cur_img_idx = self.m_img_list.index(ustr(item.text()))
        filename = self.m_img_list[self.cur_img_idx]
        if filename:
            self.load_file(filename)

    # Add chris
    def button_state(self, item=None):
        """ Function to handle difficult examples
        Update on each object """
        if not self.canvas.editing():
            return

        item = self.current_item()
        if not item:  # If not selected Item, take the first one
            item = self.label_list.item(self.label_list.count() - 1)

        difficult = self.diffc_button.isChecked()

        try:
            shape = self.items_to_shapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.set_dirty()
            else:  # User probably changed item visibility
                self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.
    def shape_selection_changed(self, selected=False):
        if self._no_selection_slot:
            self._no_selection_slot = False
        else:
            shape = self.canvas.selected_shape
            if shape:
                self.shapes_to_items[shape].setSelected(True)
            else:
                self.label_list.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def add_label(self, shape):
        shape.paint_label = self.display_label_option.isChecked()
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generate_color_by_text(shape.label))
        self.items_to_shapes[item] = shape
        self.shapes_to_items[shape] = item
        self.label_list.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        self.update_combo_box()
        # maintain recent labels list (most-recent-first, unique, cap to 9)
        if shape.label:
            try:
                self._recent_labels.remove(shape.label)
            except ValueError:
                pass
            self._recent_labels.insert(0, shape.label)
            if len(self._recent_labels) > 9:
                self._recent_labels = self._recent_labels[:9]

    def remove_label(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapes_to_items[shape]
        self.label_list.takeItem(self.label_list.row(item))
        del self.shapes_to_items[shape]
        del self.items_to_shapes[item]
        self.update_combo_box()

    def load_labels(self, shapes):
        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:

                # Ensure the labels are within the bounds of the image. If not, fix them.
                x, y, snapped = self.canvas.snap_point_to_canvas(x, y)
                if snapped:
                    self.set_dirty()

                shape.add_point(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generate_color_by_text(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generate_color_by_text(label)

            self.add_label(shape)
        self.update_combo_box()
        self.canvas.load_shapes(s)
        self.update_annotation_preview()

    def update_combo_box(self):
        # Get the unique labels and add them to the Combobox.
        items_text_list = [str(self.label_list.item(i).text()) for i in range(self.label_list.count())]

        unique_text_list = list(set(items_text_list))
        # Add a null row for showing all the labels
        unique_text_list.append("")
        unique_text_list.sort()

        self.combo_box.update_items(unique_text_list)

    # --- Filters ---
    def filter_by_class(self, class_name):
        for i in range(self.label_list.count()):
            item = self.label_list.item(i)
            if not class_name or item.text() == class_name:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def filter_unverified(self):
        # Show only if canvas.verified is False
        if self.canvas.verified:
            return
        for i in range(self.label_list.count()):
            item = self.label_list.item(i)
            item.setCheckState(Qt.Checked)

    def filter_missing_labels(self):
        # Hide items with empty label
        for i in range(self.label_list.count()):
            item = self.label_list.item(i)
            if not item.text().strip():
                item.setCheckState(Qt.Unchecked)

    def apply_filter_menu(self, which):
        if which == 'unverified':
            self.filter_unverified()
        elif which == 'missing':
            self.filter_missing_labels()
        else:
            self.filter_by_class(which)

    def _filter_show_current_class(self):
        text = self.combo_box.cb.currentText()
        self.filter_by_class(text)

    def _sort_file_list(self, alpha=False, reverse=False, depth=False):
        if not self.m_img_list:
            return
        if alpha:
            self.m_img_list.sort(key=lambda p: os.path.basename(p).lower(), reverse=reverse)
        elif depth:
            self.m_img_list.sort(key=lambda p: p.count(os.sep))
        # repopulate widget
        self.file_list_widget.clear()
        for imgPath in self.m_img_list:
            item = QListWidgetItem(imgPath)
            icon = self._thumb_cache.get(imgPath)
            if icon:
                item.setIcon(icon)
            self.file_list_widget.addItem(item)

    def _filter_files(self, text):
        text = text.strip().lower()
        self.file_list_widget.clear()
        for imgPath in self.m_img_list:
            base = os.path.basename(imgPath).lower()
            if not text or text in base:
                item = QListWidgetItem(imgPath)
                icon = self._thumb_cache.get(imgPath)
                if icon:
                    item.setIcon(icon)
                self.file_list_widget.addItem(item)

    def save_labels(self, annotation_file_path):
        annotation_file_path = ustr(annotation_file_path)
        if self.label_file is None:
            self.label_file = LabelFile()
            self.label_file.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                        # add chris
                        difficult=s.difficult)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        # Can add different annotation formats here
        try:
            if self.label_file_format == LabelFileFormat.PASCAL_VOC:
                if annotation_file_path[-4:].lower() != ".xml":
                    annotation_file_path += XML_EXT
                self.label_file.save_pascal_voc_format(annotation_file_path, shapes, self.file_path, self.image_data,
                                                       self.line_color.getRgb(), self.fill_color.getRgb())
            elif self.label_file_format == LabelFileFormat.YOLO:
                if annotation_file_path[-4:].lower() != ".txt":
                    annotation_file_path += TXT_EXT
                self.label_file.save_yolo_format(annotation_file_path, shapes, self.file_path, self.image_data, self.label_hist,
                                                 self.line_color.getRgb(), self.fill_color.getRgb())
            elif self.label_file_format == LabelFileFormat.CREATE_ML:
                if annotation_file_path[-5:].lower() != ".json":
                    annotation_file_path += JSON_EXT
                self.label_file.save_create_ml_format(annotation_file_path, shapes, self.file_path, self.image_data,
                                                      self.label_hist, self.line_color.getRgb(), self.fill_color.getRgb())
            elif self.label_file_format == LabelFileFormat.COCO:
                if annotation_file_path[-5:].lower() != ".json":
                    annotation_file_path += JSON_EXT
                self.label_file.save_coco_format(annotation_file_path, shapes, self.file_path, self.image_data,
                                                 self.label_hist, self.line_color.getRgb(), self.fill_color.getRgb())
            else:
                self.label_file.save(annotation_file_path, shapes, self.file_path, self.image_data,
                                     self.line_color.getRgb(), self.fill_color.getRgb())
            print('Image:{0} -> Annotation:{1}'.format(self.file_path, annotation_file_path))
            # Refresh preview after save
            self.update_annotation_preview()
            return True
        except LabelFileError as e:
            self.error_message(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copy_selected_shape(self):
        self.add_label(self.canvas.copy_selected_shape())
        # fix copy and delete
        self.shape_selection_changed(True)

    def combo_selection_changed(self, index):
        text = self.combo_box.cb.itemText(index)
        for i in range(self.label_list.count()):
            if text == "":
                self.label_list.item(i).setCheckState(2)
            elif text != self.label_list.item(i).text():
                self.label_list.item(i).setCheckState(0)
            else:
                self.label_list.item(i).setCheckState(2)
        # also apply filter by class to canvas visibility
        if text == "":
            self.toggle_polygons(True)
        else:
            self.filter_by_class(text)

    def default_label_combo_selection_changed(self, index):
        self.default_label=self.label_hist[index]

    def label_selection_changed(self):
        item = self.current_item()
        if item and self.canvas.editing():
            self._no_selection_slot = True
            self.canvas.select_shape(self.items_to_shapes[item])
            shape = self.items_to_shapes[item]
            # Add Chris
            self.diffc_button.setChecked(shape.difficult)

    def label_item_changed(self, item):
        shape = self.items_to_shapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generate_color_by_text(shape.label)
            self.set_dirty()
        else:  # User probably changed item visibility
            self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def new_shape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if not self.use_default_label_checkbox.isChecked():
            if len(self.label_hist) > 0:
                self.label_dialog = LabelDialog(
                    parent=self, list_item=self.label_hist)

            # Sync single class mode from PR#106
            if self.single_class_mode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.label_dialog.pop_up(text=self.prev_label_text)
                self.lastLabel = text
        else:
            text = self.default_label

        # Add Chris
        self.diffc_button.setChecked(False)
        if text is not None:
            self.prev_label_text = text
            generate_color = generate_color_by_text(text)
            shape = self.canvas.set_last_label(text, generate_color, generate_color)
            self.add_label(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.set_editing(True)
                self.actions.create.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.set_dirty()

            if text not in self.label_hist:
                self.label_hist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.reset_all_lines()

    def scroll_request(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scroll_bars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def set_zoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoom_mode = self.MANUAL_ZOOM
        # Arithmetic on scaling factor often results in float
        # Convert to int to avoid type errors
        self.zoom_widget.setValue(int(value))

    def add_zoom(self, increment=10):
        self.set_zoom(self.zoom_widget.value() + increment)

    def zoom_request(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scroll_bars[Qt.Horizontal]
        v_bar = self.scroll_bars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scroll_area.width()
        h = self.scroll_area.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta // (8 * 15)
        scale = 10
        self.add_zoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = int(h_bar.value() + move_x * d_h_bar_max)
        new_v_bar_value = int(v_bar.value() + move_y * d_v_bar_max)

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def light_request(self, delta):
        self.add_light(5*delta // (8 * 15))

    def set_fit_window(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_light(self, value):
        self.actions.lightOrg.setChecked(int(value) == 50)
        # Arithmetic on scaling factor often results in float
        # Convert to int to avoid type errors
        self.light_widget.setValue(int(value))

    def add_light(self, increment=10):
        self.set_light(self.light_widget.value() + increment)

    def toggle_polygons(self, value):
        for item, shape in self.items_to_shapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def load_file(self, file_path=None):
        """Load the specified file, or the last opened file if None."""
        self.reset_state()
        self.canvas.setEnabled(False)
        if file_path is None:
            file_path = self.settings.get(SETTING_FILENAME)
        # Make sure that filePath is a regular python string, rather than QString
        file_path = ustr(file_path)

        # Fix bug: An  index error after select a directory when open a new file.
        unicode_file_path = ustr(file_path)
        unicode_file_path = os.path.abspath(unicode_file_path)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if unicode_file_path and self.file_list_widget.count() > 0:
            if unicode_file_path in self.m_img_list:
                index = self.m_img_list.index(unicode_file_path)
                file_widget_item = self.file_list_widget.item(index)
                file_widget_item.setSelected(True)
            else:
                self.file_list_widget.clear()
                self.m_img_list.clear()

        if unicode_file_path and os.path.exists(unicode_file_path):
            if LabelFile.is_label_file(unicode_file_path):
                try:
                    self.label_file = LabelFile(unicode_file_path)
                except LabelFileError as e:
                    self.error_message(u'Error opening file',
                                       (u"<p><b>%s</b></p>"
                                        u"<p>Make sure <i>%s</i> is a valid label file.")
                                       % (e, unicode_file_path))
                    self.status("Error reading %s" % unicode_file_path)
                    
                    return False
                self.image_data = self.label_file.image_data
                self.line_color = QColor(*self.label_file.lineColor)
                self.fill_color = QColor(*self.label_file.fillColor)
                self.canvas.verified = self.label_file.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                self.image_data = read(unicode_file_path, None)
                self.label_file = None
                self.canvas.verified = False

            if isinstance(self.image_data, QImage):
                image = self.image_data
            else:
                image = QImage.fromData(self.image_data)
            if image.isNull():
                self.error_message(u'Error opening file',
                                   u"<p>Make sure <i>%s</i> is a valid image file." % unicode_file_path)
                self.status("Error reading %s" % unicode_file_path)
                return False
            self.status("Loaded %s" % os.path.basename(unicode_file_path))
            self.image = image
            self.file_path = unicode_file_path
            self.canvas.load_pixmap(QPixmap.fromImage(image))
            if self.label_file:
                self.load_labels(self.label_file.shapes)
            self.set_clean()
            self.canvas.setEnabled(True)
            self.adjust_scale(initial=True)
            self.paint_canvas()
            self.add_recent_file(self.file_path)
            self.toggle_actions(True)
            self.show_bounding_box_from_annotation_file(self.file_path)

            counter = self.counter_str()
            self.setWindowTitle(__appname__ + ' ' + file_path + ' ' + counter)

            # Default : select last item if there is at least one item
            if self.label_list.count():
                self.label_list.setCurrentItem(self.label_list.item(self.label_list.count() - 1))
                self.label_list.item(self.label_list.count() - 1).setSelected(True)

            self.canvas.setFocus(True)
            return True
        return False

    def counter_str(self):
        """
        Converts image counter to string representation.
        """
        return '[{} / {}]'.format(self.cur_img_idx + 1, self.img_count)

    def show_bounding_box_from_annotation_file(self, file_path):
        if self.default_save_dir is not None:
            basename = os.path.basename(os.path.splitext(file_path)[0])
            xml_path = os.path.join(self.default_save_dir, basename + XML_EXT)
            txt_path = os.path.join(self.default_save_dir, basename + TXT_EXT)
            json_path = os.path.join(self.default_save_dir, basename + JSON_EXT)

            """Annotation file priority:
            PascalXML > YOLO
            """
            if os.path.isfile(xml_path):
                self.load_pascal_xml_by_filename(xml_path)
            elif os.path.isfile(txt_path):
                self.load_yolo_txt_by_filename(txt_path)
            elif os.path.isfile(json_path):
                # Try COCO first, fallback to CreateML
                if not self.load_coco_json_by_filename(json_path):
                    self.load_create_ml_json_by_filename(json_path, file_path)

        else:
            xml_path = os.path.splitext(file_path)[0] + XML_EXT
            txt_path = os.path.splitext(file_path)[0] + TXT_EXT
            json_path = os.path.splitext(file_path)[0] + JSON_EXT

            if os.path.isfile(xml_path):
                self.load_pascal_xml_by_filename(xml_path)
            elif os.path.isfile(txt_path):
                self.load_yolo_txt_by_filename(txt_path)
            elif os.path.isfile(json_path):
                if not self.load_coco_json_by_filename(json_path):
                    self.load_create_ml_json_by_filename(json_path, file_path)
            

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoom_mode != self.MANUAL_ZOOM:
            self.adjust_scale()
        super(MainWindow, self).resizeEvent(event)

    def paint_canvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.overlay_color = self.light_widget.color()
        self.canvas.label_font_size = int(0.02 * max(self.image.width(), self.image.height()))
        self.canvas.adjustSize()
        self.canvas.update()
        # Also update preview when repainting (e.g., zoom/light changes don't alter shapes, so skip heavy work)

    # --- Undo/Redo ---
    def _snapshot_shapes(self):
        return [
            dict(
                label=s.label,
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                points=[(p.x(), p.y()) for p in s.points],
                difficult=s.difficult,
            )
            for s in self.canvas.shapes
        ]

    def _apply_snapshot(self, snapshot):
        # Clear and load shapes
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()
        self.label_list.clear()
        self.canvas.load_shapes([])
        self.load_labels([
            (
                shape['label'],
                shape['points'],
                shape.get('line_color'),
                shape.get('fill_color'),
                shape.get('difficult', False),
            )
            for shape in snapshot
        ])
        self.set_dirty()

    def _update_undo_redo_actions(self):
        self.actions.undo.setEnabled(len(self._history) > 0)
        self.actions.redo.setEnabled(len(self._redo) > 0)

    def _push_history_snapshot(self):
        if self._history_debounce:
            return
        self._history_debounce = True
        try:
            snap = self._snapshot_shapes()
            self._history.append(snap)
            self._redo.clear()
            self._update_undo_redo_actions()
        finally:
            QTimer.singleShot(50, lambda: setattr(self, '_history_debounce', False))

    def undo_action(self):
        if not self._history:
            return
        current = self._snapshot_shapes()
        last = self._history.pop()
        self._redo.append(current)
        self._apply_snapshot(last)
        self._update_undo_redo_actions()

    def redo_action(self):
        if not self._redo:
            return
        current = self._snapshot_shapes()
        nxt = self._redo.pop()
        self._history.append(current)
        self._apply_snapshot(nxt)
        self._update_undo_redo_actions()

    def toggle_dark_mode(self, value=True):
        # Very simple Fusion dark palette
        app = QApplication.instance()
        if not app:
            return
        if value:
            app.setStyle('Fusion')
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
        else:
            app.setPalette(QPalette())

    def on_shape_moved(self):
        self.set_dirty()

    # --- Preferences / Shortcuts dialogs ---
    def open_preferences_dialog(self):
        try:
            # Provide optional managers if available
            config_manager = None
            try:
                from core.config_manager import ConfigManager
                config_manager = ConfigManager()
                config_manager.load_config()
            except Exception:
                config_manager = None
            shortcut_manager = None
            try:
                from libs.shortcut_manager import get_shortcut_manager
                shortcut_manager = get_shortcut_manager()
                # Attach to main window to ensure QShortcut parent
                shortcut_manager.parent_widget = self
            except Exception:
                shortcut_manager = None
            dlg = PreferencesDialog(self, config_manager=config_manager, shortcut_manager=shortcut_manager)
            dlg.exec_()
        except Exception as e:
            self.error_message('Préférences', ustr(e))

    def open_shortcuts_editor(self):
        try:
            from libs.shortcut_manager import get_shortcut_manager
            sm = get_shortcut_manager()
            sm.parent_widget = self
            dlg = ShortcutsDialog(self, shortcut_manager=sm)
            if dlg.exec_():
                # Refresh cheatsheet
                self._refresh_shortcuts_cheatsheet()
        except Exception as e:
            self.error_message('Raccourcis', ustr(e))

    def _refresh_shortcuts_cheatsheet(self):
        try:
            from libs.shortcut_manager import get_shortcut_manager
            sm = get_shortcut_manager()
            lines = []
            for act in sm.get_all_actions():
                if getattr(act, 'enabled', True):
                    key = act.current_key or act.default_key or ''
                    lines.append(f"{key:8s}  {act.name}")
            for w in self.shortcuts_dock.findChildren(QPlainTextEdit):
                w.setPlainText("\n".join(lines))
        except Exception:
            pass
        self.update_annotation_preview()

    def toggle_command_palette(self):
        if self.command_palette.isVisible():
            self.command_palette.hide()
            if self.command_palette_dock:
                self.command_palette_dock.hide()
            return
        if not self.command_palette_dock:
            self.command_palette_dock = QDockWidget('Command Palette', self)
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.addWidget(self.command_palette)
            self.command_palette_dock.setWidget(w)
            self.addDockWidget(Qt.TopDockWidgetArea, self.command_palette_dock)
        self.command_palette_dock.show()
        self.command_palette.show()
        self.command_palette.setFocus()

    def _exec_command_palette(self):
        query = self.command_palette.text().strip().lower()
        if not query:
            return
        commands = {
            'open': self.open_file,
            'open dir': self.open_dir_dialog,
            'save': self.save_file,
            'next': self.open_next_image,
            'prev': self.open_prev_image,
            'verify': self.verify_image,
            'dark': lambda: self.toggle_dark_mode(True),
            'light': lambda: self.toggle_dark_mode(False),
        }
        for key, fn in commands.items():
            if key in query:
                fn()
                break

    def adjust_scale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoom_mode]()
        self.zoom_widget.setValue(int(100 * value))

    def scale_fit_window(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scale_fit_width(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.may_continue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the beginning
        if self.dir_name is None:
            settings[SETTING_FILENAME] = self.file_path if self.file_path else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.line_color
        settings[SETTING_FILL_COLOR] = self.fill_color
        settings[SETTING_RECENT_FILES] = self.recent_files
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        settings[SETTING_DARK_MODE] = bool(getattr(self, '_dark_mode_action', None) and self._dark_mode_action.isChecked())
        if self.default_save_dir and os.path.exists(self.default_save_dir):
            settings[SETTING_SAVE_DIR] = ustr(self.default_save_dir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.last_open_dir and os.path.exists(self.last_open_dir):
            settings[SETTING_LAST_OPEN_DIR] = self.last_open_dir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        settings[SETTING_AUTO_SAVE] = self.auto_saving.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.single_class_mode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.display_label_option.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.draw_squares_option.isChecked()
        settings[SETTING_LABEL_FILE_FORMAT] = self.label_file_format
        # persist locale if user switched it
        if hasattr(self, '_current_locale') and self._current_locale:
            settings[SETTING_LOCALE] = self._current_locale
        settings.save()

    def load_recent(self, filename):
        if self.may_continue():
            self.load_file(filename)

    def scan_all_images(self, folder_path):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relative_path = os.path.join(root, file)
                    path = ustr(os.path.abspath(relative_path))
                    images.append(path)
                    # build thumbnail icons lazily
                    try:
                        if path not in self._thumb_cache:
                            pix = QPixmap(path)
                            if not pix.isNull():
                                self._thumb_cache[path] = QIcon(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    except Exception:
                        pass
        natural_sort(images, key=lambda x: x.lower())
        return images

    def change_save_dir_dialog(self, _value=False):
        if self.default_save_dir is not None:
            path = ustr(self.default_save_dir)
        else:
            path = '.'

        dir_path = ustr(QFileDialog.getExistingDirectory(self,
                                                         '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                         | QFileDialog.DontResolveSymlinks))

        if dir_path is not None and len(dir_path) > 1:
            self.default_save_dir = dir_path

        self.show_bounding_box_from_annotation_file(self.file_path)

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.default_save_dir))
        self.statusBar().show()


    def open_annotation_dialog(self, _value=False):
        if self.file_path is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.file_path))\
            if self.file_path else '.'
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self, '%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.load_pascal_xml_by_filename(filename)

        elif self.label_file_format == LabelFileFormat.CREATE_ML:
            
            filters = "Open Annotation JSON file (%s)" % ' '.join(['*.json'])
            filename = ustr(QFileDialog.getOpenFileName(self, '%s - Choose a json file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]

            self.load_create_ml_json_by_filename(filename, self.file_path)         
        
    def open_class_manager(self, _value=False):
        dlg = ClassManagerDialog(self.label_hist, parent=self)
        if dlg.exec_():
            self.label_hist = dlg.get_classes()
            # refresh default label combo and filter combo
            self.default_label_combo_box.items = self.label_hist
            self.default_label_combo_box.cb.clear()
            self.default_label_combo_box.cb.addItems(self.label_hist)
            self.update_combo_box()

    def export_shortcuts(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export Shortcuts', self.current_path(), 'JSON (*.json)')
        if not path:
            return
        data = {
            'save': 'Ctrl+S',
            'open': 'Ctrl+O',
            'open_dir': 'Ctrl+U',
            'undo': 'Ctrl+Z',
            'redo': 'Ctrl+Shift+Z',
            'palette': 'Ctrl+P',
        }
        try:
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.error_message('Export Shortcuts', ustr(e))

    def import_shortcuts(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import Shortcuts', self.current_path(), 'JSON (*.json)')
        if not path:
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Placeholder: store metadata for future full remapping
            self.settings['custom_shortcuts'] = data
            self.statusBar().showMessage('Shortcuts imported. Some changes may require restart.', 5000)
        except Exception as e:
            self.error_message('Import Shortcuts', ustr(e))

    def open_dir_dialog(self, _value=False, dir_path=None, silent=False):
        if not self.may_continue():
            return

        default_open_dir_path = dir_path if dir_path else '.'
        if self.last_open_dir and os.path.exists(self.last_open_dir):
            default_open_dir_path = self.last_open_dir
        else:
            default_open_dir_path = os.path.dirname(self.file_path) if self.file_path else '.'
        if silent != True:
            target_dir_path = ustr(QFileDialog.getExistingDirectory(self,
                                                                    '%s - Open Directory' % __appname__, default_open_dir_path,
                                                                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        else:
            target_dir_path = ustr(default_open_dir_path)
        self.last_open_dir = target_dir_path
        self.import_dir_images(target_dir_path)
        self.default_save_dir = target_dir_path
        if self.file_path:
            self.show_bounding_box_from_annotation_file(file_path=self.file_path)

    def import_dir_images(self, dir_path):
        if not self.may_continue() or not dir_path:
            return

        self.last_open_dir = dir_path
        self.dir_name = dir_path
        self.file_path = None
        self.file_list_widget.clear()

        # Progress dialog during scan and list population
        progress = QProgressDialog('Import des images...', 'Annuler', 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(300)
        progress.show()

        # Scan
        self.m_img_list = self.scan_all_images(dir_path)
        self.img_count = len(self.m_img_list)

        # Update progress range and populate
        progress.setLabelText('Chargement des vignettes...')
        progress.setRange(0, self.img_count if self.img_count > 0 else 1)

        self.open_next_image()
        for i, imgPath in enumerate(self.m_img_list):
            if progress.wasCanceled():
                break
            item = QListWidgetItem(imgPath)
            # set thumbnail icon if available
            icon = self._thumb_cache.get(imgPath)
            if icon:
                item.setIcon(icon)
            self.file_list_widget.addItem(item)
            progress.setValue(i + 1)

        progress.close()

    def batch_rename_images(self):
        # Ensure a directory is loaded
        if not self.dir_name or not os.path.isdir(self.dir_name):
            self.statusBar().showMessage('Ouvrez d\'abord un dossier (Open Dir).')
            self.statusBar().show()
            return
        # Ask base name
        base, ok = QInputDialog.getText(self, 'Renommer les images', 'Nom de base (ex: cacao):')
        if not ok or not base.strip():
            return
        base = base.strip()

        # Ask starting index
        total = len(self.m_img_list)
        start_idx, ok = QInputDialog.getInt(self, 'Index de départ', 'Commencer à:', 1, 0, 10**6, 1)
        if not ok:
            return
        # Ask separator
        sep, ok = QInputDialog.getText(self, 'Séparateur', 'Séparateur entre le nom et le numéro (ex: _):', text='')
        if not ok:
            return
        # Ask zero padding
        default_pad = len(str(total))
        pad, ok = QInputDialog.getInt(self, 'Zéro-padding', 'Nombre de chiffres (ex: %d):' % default_pad, default_pad, 1, 10, 1)
        if not ok:
            return

        # Confirm
        reply = QMessageBox.question(self, 'Confirmer',
                                     'Renommer %d images avec le préfixe "%s" et un compteur ?' % (total, base),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # Progress
        progress = QProgressDialog('Renommage des images...', 'Annuler', 0, total, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(300)
        progress.show()

        # Build extension sets and associated annotation paths
        new_paths = []
        for offset, old_path in enumerate(self.m_img_list):
            if progress.wasCanceled():
                break
            dirp = os.path.dirname(old_path)
            ext = os.path.splitext(old_path)[1]
            num = start_idx + offset
            new_name = f"{base}{sep}{str(num).zfill(pad)}{ext}"
            new_path = os.path.join(dirp, new_name)
            # If target exists, skip
            if os.path.exists(new_path):
                new_paths.append(old_path)
                progress.setValue(offset + 1)
                continue
            # Compute annotation paths (in save dir if configured, else alongside)
            def anno_candidates(img_path):
                root = os.path.splitext(img_path)[0]
                return [root + XML_EXT, root + TXT_EXT, root + JSON_EXT]
            if self.default_save_dir:
                old_annos = [os.path.join(self.default_save_dir, os.path.splitext(os.path.basename(old_path))[0] + s) for s in [XML_EXT, TXT_EXT, JSON_EXT]]
                new_annos = [os.path.join(self.default_save_dir, os.path.splitext(new_name)[0] + s) for s in [XML_EXT, TXT_EXT, JSON_EXT]]
            else:
                old_annos = anno_candidates(old_path)
                new_annos = [os.path.splitext(new_path)[0] + s for s in [XML_EXT, TXT_EXT, JSON_EXT]]

            # Rename file and annotations if they exist
            try:
                os.rename(old_path, new_path)
                for oa, na in zip(old_annos, new_annos):
                    if os.path.exists(oa):
                        try:
                            os.rename(oa, na)
                        except Exception:
                            pass
                new_paths.append(new_path)
            except Exception as e:
                new_paths.append(old_path)
            progress.setValue(offset + 1)

        progress.close()
        # Update internal list, refresh UI
        if new_paths:
            self.m_img_list = new_paths
            self.img_count = len(self.m_img_list)
            self.file_list_widget.clear()
            for imgPath in self.m_img_list:
                item = QListWidgetItem(imgPath)
                icon = self._thumb_cache.get(imgPath)
                if icon:
                    item.setIcon(icon)
                self.file_list_widget.addItem(item)
            # reload current index safely
            if 0 <= self.cur_img_idx < self.img_count:
                self.load_file(self.m_img_list[self.cur_img_idx])
            else:
                self.cur_img_idx = 0
                if self.m_img_list:
                    self.load_file(self.m_img_list[0])

    def verify_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if self.file_path is not None:
            try:
                self.label_file.toggle_verify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.save_file()
                if self.label_file is not None:
                    self.label_file.toggle_verify()
                else:
                    return

            self.canvas.verified = self.label_file.verified
            self.paint_canvas()
            self.save_file()

    def open_prev_image(self, _value=False):
        # Proceeding prev image without dialog if having any label
        if self.auto_saving.isChecked():
            if self.default_save_dir is not None:
                if self.dirty is True:
                    try:
                        self.save_file()
                    except Exception as e:
                        self.statusBar().showMessage('Auto-save failed: %s' % ustr(e))
                        self.statusBar().show()
            else:
                self.change_save_dir_dialog()
                return

        if not self.may_continue():
            return

        if self.img_count <= 0:
            return

        if self.file_path is None:
            return

        if self.cur_img_idx - 1 >= 0:
            self.cur_img_idx -= 1
            filename = self.m_img_list[self.cur_img_idx]
            if filename:
                self.load_file(filename)
                # Preload previous previous (two-steps back) to keep history warm
                try:
                    if self.cur_img_idx - 1 >= 0:
                        prv = self.m_img_list[self.cur_img_idx - 1]
                        _ = QPixmap(prv)
                except Exception:
                    pass

    def open_next_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if self.auto_saving.isChecked():
            if self.default_save_dir is not None:
                if self.dirty is True:
                    try:
                        self.save_file()
                    except Exception as e:
                        self.statusBar().showMessage('Auto-save failed: %s' % ustr(e))
                        self.statusBar().show()
            else:
                self.change_save_dir_dialog()
                return

        if not self.may_continue():
            return

        if self.img_count <= 0:
            return
        
        if not self.m_img_list:
            return

        filename = None
        if self.file_path is None:
            filename = self.m_img_list[0]
            self.cur_img_idx = 0
        else:
            if self.cur_img_idx + 1 < self.img_count:
                self.cur_img_idx += 1
                filename = self.m_img_list[self.cur_img_idx]

        if filename:
            self.load_file(filename)
            # Preload next image pixmap in background cache for snappy switch
            try:
                if self.cur_img_idx + 1 < self.img_count:
                    nxt = self.m_img_list[self.cur_img_idx + 1]
                    if self._next_image_cache != nxt:
                        _ = QPixmap(nxt)  # warm filesystem cache
                        self._next_image_cache = nxt
            except Exception:
                pass

    def open_file(self, _value=False):
        if not self.may_continue():
            return
        path = os.path.dirname(ustr(self.file_path)) if self.file_path else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename,_ = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.cur_img_idx = 0
            self.img_count = 1
            self.load_file(filename)

    def save_file(self, _value=False):
        if self.default_save_dir is not None and len(ustr(self.default_save_dir)):
            if self.file_path:
                image_file_name = os.path.basename(self.file_path)
                saved_file_name = os.path.splitext(image_file_name)[0]
                saved_path = os.path.join(ustr(self.default_save_dir), saved_file_name)
                self._save_file(saved_path)
        else:
            image_file_dir = os.path.dirname(self.file_path)
            image_file_name = os.path.basename(self.file_path)
            saved_file_name = os.path.splitext(image_file_name)[0]
            saved_path = os.path.join(image_file_dir, saved_file_name)
            self._save_file(saved_path if self.label_file
                            else self.save_file_dialog(remove_ext=False))

    def save_file_as(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._save_file(self.save_file_dialog())

    def save_file_dialog(self, remove_ext=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        open_dialog_path = self.current_path()
        dlg = QFileDialog(self, caption, open_dialog_path, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filename_without_extension = os.path.splitext(self.file_path)[0]
        dlg.selectFile(filename_without_extension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            full_file_path = ustr(dlg.selectedFiles()[0])
            if remove_ext:
                return os.path.splitext(full_file_path)[0]  # Return file path without the extension.
            else:
                return full_file_path
        return ''

    def _save_file(self, annotation_file_path):
        if annotation_file_path and self.save_labels(annotation_file_path):
            self.set_clean()
            self.statusBar().showMessage('Saved to  %s' % annotation_file_path)
            self.statusBar().show()
            self.update_annotation_preview()

    def close_file(self, _value=False):
        if not self.may_continue():
            return
        self.reset_state()
        self.set_clean()
        self.toggle_actions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def delete_image(self):
        delete_path = self.file_path
        if not delete_path:
            return
        idx = self.cur_img_idx
        if os.path.exists(delete_path):
            try:
                os.remove(delete_path)
            except Exception as e:
                self.statusBar().showMessage('Delete failed: %s' % ustr(e))
                self.statusBar().show()
                return
        # Refresh directory listing and thumbnails
        self.import_dir_images(self.last_open_dir)
        n = len(self.m_img_list)
        if n <= 0:
            self.close_file()
            return
        # Clamp index to valid range
        self.cur_img_idx = max(0, min(idx, n - 1))
        if 0 <= self.cur_img_idx < n:
            filename = self.m_img_list[self.cur_img_idx]
            if filename:
                self.load_file(filename)

    def reset_all(self):
        self.settings.reset()
        self.close()
        process = QProcess()
        process.startDetached(os.path.abspath(__file__))

    def may_continue(self):
        if not self.dirty:
            return True
        else:
            discard_changes = self.discard_changes_dialog()
            if discard_changes == QMessageBox.No:
                return True
            elif discard_changes == QMessageBox.Yes:
                self.save_file()
                return True
            else:
                return False

    def discard_changes_dialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        msg = u'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, u'Attention', msg, yes | no | cancel)

    def error_message(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def current_path(self):
        return os.path.dirname(self.file_path) if self.file_path else '.'

    def choose_color1(self):
        color = self.color_dialog.getColor(self.line_color, u'Choose line color',
                                           default=DEFAULT_LINE_COLOR)
        if color:
            self.line_color = color
            Shape.line_color = color
            self.canvas.set_drawing_color(color)
            self.canvas.update()
            self.set_dirty()

    def delete_selected_shape(self):
        deleted = self.canvas.delete_selected()
        if deleted:
            self.remove_label(deleted)
            self.set_dirty()
        if self.no_shapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def choose_shape_line_color(self):
        color = self.color_dialog.getColor(self.line_color, u'Choose Line Color',
                                           default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selected_shape.line_color = color
            self.canvas.update()
            self.set_dirty()

    def choose_shape_fill_color(self):
        color = self.color_dialog.getColor(self.fill_color, u'Choose Fill Color',
                                           default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selected_shape.fill_color = color
            self.canvas.update()
            self.set_dirty()

    def copy_shape(self):
        if self.canvas.selected_shape is None:
            # True if one accidentally touches the left mouse button before releasing
            return
        self.canvas.end_move(copy=True)
        self.add_label(self.canvas.selected_shape)
        self.set_dirty()

    def move_shape(self):
        self.canvas.end_move(copy=False)
        self.set_dirty()

    def load_predefined_classes(self, predef_classes_file):
        if os.path.exists(predef_classes_file) is True:
            with codecs.open(predef_classes_file, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.label_hist is None:
                        self.label_hist = [line]
                    else:
                        self.label_hist.append(line)

    def load_pascal_xml_by_filename(self, xml_path):
        if self.file_path is None:
            return
        if os.path.isfile(xml_path) is False:
            return

        self.set_format(FORMAT_PASCALVOC)

        t_voc_parse_reader = PascalVocReader(xml_path)
        shapes = t_voc_parse_reader.get_shapes()
        self.load_labels(shapes)
        self.canvas.verified = t_voc_parse_reader.verified

    def load_yolo_txt_by_filename(self, txt_path):
        if self.file_path is None:
            return
        if os.path.isfile(txt_path) is False:
            return

        self.set_format(FORMAT_YOLO)
        try:
            t_yolo_parse_reader = YoloReader(txt_path, self.image)
            shapes = t_yolo_parse_reader.get_shapes()
            self.load_labels(shapes)
            self.canvas.verified = t_yolo_parse_reader.verified
        except (FileNotFoundError, ValueError, IOError) as e:
            self.error_message('YOLO Error', u'<b>%s</b>' % ustr(e))

    def load_create_ml_json_by_filename(self, json_path, file_path):
        if self.file_path is None:
            return
        if os.path.isfile(json_path) is False:
            return

        self.set_format(FORMAT_CREATEML)

        create_ml_parse_reader = CreateMLReader(json_path, file_path)
        shapes = create_ml_parse_reader.get_shapes()
        self.load_labels(shapes)
        self.canvas.verified = create_ml_parse_reader.verified

    def load_coco_json_by_filename(self, json_path):
        try:
            reader = CocoReader(json_path)
            shapes = reader.get_shapes()
            if not shapes:
                return False
            self.set_format(FORMAT_COCO)
            self.load_labels(shapes)
            self.canvas.verified = False
            return True
        except Exception:
            return False

    def copy_previous_bounding_boxes(self):
        current_index = self.m_img_list.index(self.file_path)
        if current_index - 1 >= 0:
            prev_file_path = self.m_img_list[current_index - 1]
            self.show_bounding_box_from_annotation_file(prev_file_path)
            self.save_file()

    def toggle_paint_labels_option(self):
        for shape in self.canvas.shapes:
            shape.paint_label = self.display_label_option.isChecked()

    def toggle_draw_square(self):
        self.canvas.set_drawing_shape_to_square(self.draw_squares_option.isChecked())

    # --- Annotation preview rendering ---
    def _collect_current_shapes_dict(self):
        def fmt(s):
            return dict(
                label=s.label,
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                points=[(p.x(), p.y()) for p in s.points],
                difficult=s.difficult,
            )
        return [fmt(s) for s in self.canvas.shapes]

    def update_annotation_preview(self):
        try:
            if not hasattr(self, 'preview_text') or self.preview_text is None:
                return
            shapes = self._collect_current_shapes_dict()
            if not self.file_path or not shapes:
                self.preview_text.setPlainText('')
                return
            # Build a preview according to current selected format
            fmt = self.label_file_format
            if fmt == LabelFileFormat.PASCAL_VOC:
                # Build minimal Pascal VOC XML preview
                from xml.etree.ElementTree import Element, SubElement, tostring
                top = Element('annotation')
                folder = SubElement(top, 'folder'); folder.text = os.path.basename(os.path.dirname(self.file_path))
                filename = SubElement(top, 'filename'); filename.text = os.path.basename(self.file_path)
                size = SubElement(top, 'size')
                SubElement(size, 'width').text = str(self.image.width())
                SubElement(size, 'height').text = str(self.image.height())
                SubElement(size, 'depth').text = '3'
                for s in shapes:
                    obj = SubElement(top, 'object')
                    SubElement(obj, 'name').text = s['label']
                    bb = SubElement(obj, 'bndbox')
                    xs = [p[0] for p in s['points']]; ys = [p[1] for p in s['points']]
                    SubElement(bb, 'xmin').text = str(int(min(xs)))
                    SubElement(bb, 'ymin').text = str(int(min(ys)))
                    SubElement(bb, 'xmax').text = str(int(max(xs)))
                    SubElement(bb, 'ymax').text = str(int(max(ys)))
                text = tostring(top, encoding='unicode')
                self.preview_text.setPlainText(text)
            elif fmt == LabelFileFormat.YOLO:
                # YOLO txt preview (multiple lines)
                lines = []
                classes = list(self.label_hist)
                for s in shapes:
                    xs = [p[0] for p in s['points']]; ys = [p[1] for p in s['points']]
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)
                    x_center = ((x_min + x_max) / 2) / self.image.width()
                    y_center = ((y_min + y_max) / 2) / self.image.height()
                    w = (x_max - x_min) / self.image.width()
                    h = (y_max - y_min) / self.image.height()
                    if s['label'] not in classes:
                        classes.append(s['label'])
                    idx = classes.index(s['label'])
                    lines.append(f"{idx} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")
                text = '\n'.join(lines)
                self.preview_text.setPlainText(text)
            elif fmt == LabelFileFormat.CREATE_ML:
                # CreateML snippet for current image only
                anns = []
                for s in shapes:
                    xs = [p[0] for p in s['points']]; ys = [p[1] for p in s['points']]
                    x1, x2 = min(xs), max(xs); y1, y2 = min(ys), max(ys)
                    width = x2 - x1; height = y2 - y1
                    x = x1 + width / 2; y = y1 + height / 2
                    anns.append({
                        'label': s['label'],
                        'coordinates': {'x': x, 'y': y, 'width': width, 'height': height}
                    })
                data = [{
                    'image': os.path.basename(self.file_path),
                    'verified': self.canvas.verified,
                    'annotations': anns,
                }]
                self.preview_text.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
            elif fmt == LabelFileFormat.COCO:
                # Minimal COCO single-image preview
                cats = []
                cat_to_id = {}
                for lab in self.label_hist:
                    if lab and lab not in cat_to_id:
                        cat_to_id[lab] = len(cat_to_id) + 1
                        cats.append({'id': cat_to_id[lab], 'name': lab, 'supercategory': 'object'})
                anns = []
                ann_id = 1
                for s in shapes:
                    xs = [p[0] for p in s['points']]; ys = [p[1] for p in s['points']]
                    x1, x2 = min(xs), max(xs); y1, y2 = min(ys), max(ys)
                    w = max(0.0, x2 - x1); h = max(0.0, y2 - y1)
                    cat = cat_to_id.get(s['label']) or cat_to_id.setdefault(s['label'], len(cat_to_id) + 1)
                    anns.append({'id': ann_id, 'image_id': 1, 'category_id': cat, 'bbox': [x1, y1, w, h], 'area': float(w*h), 'iscrowd': 0, 'segmentation': []})
                    ann_id += 1
                data = {
                    'images': [{'id': 1, 'file_name': os.path.basename(self.file_path), 'width': self.image.width(), 'height': self.image.height()}],
                    'categories': cats,
                    'annotations': anns,
                }
                self.preview_text.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            # Fail silently to avoid interrupting labeling
            try:
                self.preview_text.setPlainText('Preview error: ' + ustr(e))
            except Exception:
                pass

    # --- Drag & Drop Support ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            try:
                urls = event.mimeData().urls()
                if urls:
                    event.acceptProposedAction()
                    return
            except Exception:
                pass
        event.ignore()

    def dropEvent(self, event):
        try:
            paths = []
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local:
                    paths.append(local)
        except Exception:
            return

        if not paths:
            return

        first = paths[0]
        if os.path.isdir(first):
            self.open_dir_dialog(dir_path=first, silent=True)
            return

        # If a file: decide action based on extension
        ext = os.path.splitext(first)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff', '.webp']:
            self.load_file_async(first)
            return
        if ext == XML_EXT:
            self.load_pascal_xml_by_filename(first)
            return
        if ext == TXT_EXT:
            self.load_yolo_txt_by_filename(first)
            return
        if ext == JSON_EXT:
            # Try CreateML first (current behavior)
            self.load_create_ml_json_by_filename(first, first)
            return

    # --- Background image loading ---
    def load_file_async(self, file_path=None):
        """Load image data off the UI thread and apply when ready."""
        if file_path is None:
            file_path = self.settings.get(SETTING_FILENAME)
        file_path = ustr(file_path)
        if not file_path:
            return False

        # cancel/cleanup previous loader
        try:
            if self._image_loader and self._image_loader.isRunning():
                self._image_loader.terminate()
        except Exception:
            pass

        self.reset_state()
        self.canvas.setEnabled(False)
        self.status("Loading %s ..." % os.path.basename(file_path))

        class _Loader(QThread):
            def __init__(self, path):
                super(_Loader, self).__init__()
                self.path = path
                self.result = None
            def run(self):
                try:
                    reader = QImageReader(self.path)
                    reader.setAutoTransform(True)
                    img = reader.read()
                    self.result = img
                except Exception:
                    self.result = None

        loader = _Loader(file_path)
        self._image_loader = loader
        self._loading_path = file_path

        def _apply():
            image = loader.result
            unicode_file_path = os.path.abspath(file_path)
            if image is None or image.isNull():
                self.error_message(u'Error opening file', u"<p>Make sure <i>%s</i> is a valid image file." % unicode_file_path)
                self.status("Error reading %s" % unicode_file_path)
                return False
            # mimic synchronous path from load_file after QImage ready
            self.status("Loaded %s" % os.path.basename(unicode_file_path))
            self.image = image
            self.file_path = unicode_file_path
            self.canvas.load_pixmap(QPixmap.fromImage(image))
            self.set_clean()
            self.canvas.setEnabled(True)
            self.adjust_scale(initial=True)
            self.paint_canvas()
            self.add_recent_file(self.file_path)
            self.toggle_actions(True)
            self.show_bounding_box_from_annotation_file(self.file_path)
            counter = self.counter_str()
            self.setWindowTitle(__appname__ + ' ' + self.file_path + ' ' + counter)
            if self.label_list.count():
                self.label_list.setCurrentItem(self.label_list.item(self.label_list.count() - 1))
                self.label_list.item(self.label_list.count() - 1).setSelected(True)
            self.canvas.setFocus(True)
            return True

        loader.finished.connect(_apply)
        loader.start()
        return True

def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        reader = QImageReader(filename)
        reader.setAutoTransform(True)
        return reader.read()
    except:
        return default


def get_main_app(argv=None):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    if not argv:
        argv = []
    # Enable HiDPI scaling for crisp rendering on 4K/retina
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(new_icon("app"))
    # Splash screen with green background and title/logo
    try:
        width, height = 480, 280
        splash_pix = QPixmap(width, height)
        splash_pix.fill(QColor(25, 135, 84))  # Bootstrap green
        # Paint logo and title
        painter = QPainter(splash_pix)
        painter.setRenderHint(QPainter.Antialiasing)
        # Draw app icon if available
        icon = new_icon("app").pixmap(96, 96)
        if not icon.isNull():
            x = (width - icon.width()) // 2
            y = (height // 2) - icon.height()
            painter.drawPixmap(x, y, icon)
        # Draw title text
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        rect = QRect(0, height // 2, width, height // 2)
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignVCenter, __appname__)
        painter.end()

        splash = QSplashScreen(splash_pix)
        splash.show()
        app.processEvents()

        # Helper pour afficher une progression réelle par étapes
        def _progress(msg, pct):
            try:
                splash.showMessage(f"{msg} {pct}%", Qt.AlignHCenter | Qt.AlignBottom, Qt.white)
                app.processEvents()
            except Exception:
                pass
    except Exception:
        splash = None
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    argparser = argparse.ArgumentParser()
    argparser.add_argument("image_dir", nargs="?")
    argparser.add_argument("class_file",
                           default=os.path.join(os.path.dirname(__file__), "data", "predefined_classes.txt"),
                           nargs="?")
    argparser.add_argument("save_dir", nargs="?")
    args = argparser.parse_args(argv[1:])

    args.image_dir = args.image_dir and os.path.normpath(args.image_dir)
    args.class_file = args.class_file and os.path.normpath(args.class_file)
    args.save_dir = args.save_dir and os.path.normpath(args.save_dir)

    # Mise à jour du splash par étapes (progression réelle)
    try:
        _progress("Initialisation Qt...", 10)
        # Charger paramètres utilisateur
        try:
            settings_probe = Settings()
            settings_probe.load()
            _progress("Chargement des paramètres...", 30)
        except Exception:
            _progress("Chargement des paramètres...", 30)

        # Précharger icône/app
        try:
            _ = new_icon("app").pixmap(96, 96)
            _progress("Chargement des ressources...", 50)
        except Exception:
            _progress("Chargement des ressources...", 50)

        # Lecture classes prédéfinies si fichier fourni
        try:
            if args.class_file and os.path.exists(args.class_file):
                with codecs.open(args.class_file, 'r', 'utf8') as f:
                    _ = [ln.strip() for ln in f if ln.strip()]
                _progress("Chargement des classes...", 70)
            else:
                _progress("Chargement des classes...", 70)
        except Exception:
            _progress("Chargement des classes...", 70)
    except Exception:
        pass

    # Usage : labelImg.py image classFile saveDir
    win = MainWindow(args.image_dir,
                     args.class_file,
                     args.save_dir)
    try:
        _progress("Préparation de l'interface...", 90)
        _progress("Prêt", 100)
    except Exception:
        pass

    def _show_main_window():
        try:
            if splash:
                splash.finish(win)
        except Exception:
            pass
        win.show()

    # Retarde complètement l'apparition de la fenêtre principale jusqu'à la fin du chargement
    QTimer.singleShot(5000, _show_main_window)
    return app, win


def main():
    """construct main app and run it"""
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())
