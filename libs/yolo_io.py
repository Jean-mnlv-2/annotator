#!/usr/bin/env python
# -*- coding: utf8 -*-
import codecs
import os
from typing import List, Tuple, Optional, Any

from libs.constants import DEFAULT_ENCODING

TXT_EXT = '.txt'
ENCODE_METHOD = DEFAULT_ENCODING

class YOLOWriter:

    def __init__(self, folder_name: str, filename: str, img_size: Tuple[int, int, int], database_src: str = 'Unknown', local_img_path: Optional[str] = None):
        self.folder_name = folder_name
        self.filename = filename
        self.database_src = database_src
        self.img_size = img_size
        self.box_list = []
        self.local_img_path = local_img_path
        self.verified = False

    def add_bnd_box(self, x_min: int, y_min: int, x_max: int, y_max: int, name: str, difficult: int) -> None:
        # Guards: ensure coordinates are within image logical bounds and min<=max
        if x_min > x_max or y_min > y_max:
            raise ValueError('Invalid bounding box: min must be <= max')
        if not isinstance(name, str) or not name:
            raise ValueError('Invalid class name for bounding box')
        bnd_box = {'xmin': x_min, 'ymin': y_min, 'xmax': x_max, 'ymax': y_max}
        bnd_box['name'] = name
        bnd_box['difficult'] = difficult
        self.box_list.append(bnd_box)

    def bnd_box_to_yolo_line(self, box: dict, class_list: List[str] = []) -> Tuple[int, float, float, float, float]:
        x_min = box['xmin']
        x_max = box['xmax']
        y_min = box['ymin']
        y_max = box['ymax']

        x_center = float((x_min + x_max)) / 2 / self.img_size[1]
        y_center = float((y_min + y_max)) / 2 / self.img_size[0]

        w = float((x_max - x_min)) / self.img_size[1]
        h = float((y_max - y_min)) / self.img_size[0]

        # PR387
        box_name = box['name']
        if box_name not in class_list:
            class_list.append(box_name)

        class_index = class_list.index(box_name)

        return class_index, x_center, y_center, w, h

    def save(self, class_list: List[str] = [], target_file: Optional[str] = None) -> None:

        out_file = None  # Update yolo .txt
        out_class_file = None   # Update class list .txt

        try:
            if target_file is None:
                out_file = codecs.open(self.filename + TXT_EXT, 'w', encoding=ENCODE_METHOD)
                classes_file = os.path.join(os.path.dirname(os.path.abspath(self.filename)), "classes.txt")
                out_class_file = codecs.open(classes_file, 'w', encoding=ENCODE_METHOD)
            else:
                out_file = codecs.open(target_file, 'w', encoding=ENCODE_METHOD)
                classes_file = os.path.join(os.path.dirname(os.path.abspath(target_file)), "classes.txt")
                out_class_file = codecs.open(classes_file, 'w', encoding=ENCODE_METHOD)


            for box in self.box_list:
                class_index, x_center, y_center, w, h = self.bnd_box_to_yolo_line(box, class_list)
                out_file.write("%d %.6f %.6f %.6f %.6f\n" % (class_index, x_center, y_center, w, h))

            for c in class_list:
                out_class_file.write(c + '\n')
        except OSError as e:
            raise IOError(f'Failed to write YOLO files: {e}')
        finally:
            try:
                if out_class_file:
                    out_class_file.close()
            except Exception:
                pass
            try:
                if out_file:
                    out_file.close()
            except Exception:
                pass



class YoloReader:

    def __init__(self, file_path: str, image: Any, class_list_path: Optional[str] = None):
        # shapes type:
        # [labbel, [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], color, color, difficult]
        self.shapes = []
        self.file_path = file_path

        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f'YOLO annotation file not found: {self.file_path}')

        if class_list_path is None:
            dir_path = os.path.dirname(os.path.realpath(self.file_path))
            self.class_list_path = os.path.join(dir_path, "classes.txt")
        else:
            self.class_list_path = class_list_path

        if not os.path.exists(self.class_list_path):
            raise FileNotFoundError(f'YOLO classes file not found: {self.class_list_path}')
        with codecs.open(self.class_list_path, 'r', encoding=ENCODE_METHOD) as classes_file:
            content = classes_file.read().strip('\n')
            self.classes = content.split('\n') if content else []
        if not self.classes:
            raise ValueError('YOLO classes list is empty')

        # print (self.classes)

        img_size = [image.height(), image.width(),
                    1 if image.isGrayscale() else 3]

        self.img_size = img_size

        self.verified = False
        # try:
        self.parse_yolo_format()
        # except:
        #     pass

    def get_shapes(self) -> list:
        return self.shapes

    def add_shape(self, label: str, x_min: int, y_min: int, x_max: int, y_max: int, difficult: bool) -> None:

        points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
        self.shapes.append((label, points, None, None, difficult))

    def yolo_line_to_shape(self, class_index: str, x_center: str, y_center: str, w: str, h: str) -> Tuple[str, int, int, int, int]:
        label = self.classes[int(class_index)]

        x_min = max(float(x_center) - float(w) / 2, 0)
        x_max = min(float(x_center) + float(w) / 2, 1)
        y_min = max(float(y_center) - float(h) / 2, 0)
        y_max = min(float(y_center) + float(h) / 2, 1)

        x_min = round(self.img_size[1] * x_min)
        x_max = round(self.img_size[1] * x_max)
        y_min = round(self.img_size[0] * y_min)
        y_max = round(self.img_size[0] * y_max)

        return label, x_min, y_min, x_max, y_max

    def parse_yolo_format(self) -> None:
        with codecs.open(self.file_path, 'r', encoding=ENCODE_METHOD) as bnd_box_file:
            for raw in bnd_box_file:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(' ')
                if len(parts) != 5:
                    # Skip malformed lines gracefully
                    continue
                try:
                    class_index, x_center, y_center, w, h = parts
                    label, x_min, y_min, x_max, y_max = self.yolo_line_to_shape(class_index, x_center, y_center, w, h)
                except Exception:
                    # Skip lines that cannot be parsed (invalid floats/indices)
                    continue
                # Caveat: difficult flag is discarded when saved as yolo format.
                self.add_shape(label, x_min, y_min, x_max, y_max, False)
