#!/usr/bin/env python
# -*- coding: utf8 -*-
import json
from typing import List, Dict, Any, Tuple, Optional


class CocoWriter:

    def __init__(self, image_filename: str, image_size: Tuple[int, int, int], categories: List[str]):
        self.image_filename = image_filename
        self.image_height = int(image_size[0])
        self.image_width = int(image_size[1])
        # map categories to ids starting at 1
        self.categories = [c for c in categories if c]
        self.category_to_id = {name: idx + 1 for idx, name in enumerate(self.categories)}

    def _shape_to_bbox(self, points: List[Tuple[float, float]]):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min = float(min(xs))
        y_min = float(min(ys))
        x_max = float(max(xs))
        y_max = float(max(ys))
        return [x_min, y_min, max(0.0, x_max - x_min), max(0.0, y_max - y_min)]

    def build(self, shapes: List[Dict[str, Any]]) -> Dict[str, Any]:
        images = [
            {
                'id': 1,
                'file_name': self.image_filename,
                'width': self.image_width,
                'height': self.image_height,
            }
        ]

        categories = [
            {
                'id': cid,
                'name': name,
                'supercategory': 'object'
            }
            for name, cid in self.category_to_id.items()
        ]

        annotations = []
        ann_id = 1
        for shape in shapes:
            label = shape['label']
            if label not in self.category_to_id:
                # skip shapes for labels not in categories
                continue
            bbox = self._shape_to_bbox(shape['points'])
            area = float(bbox[2] * bbox[3])
            annotations.append({
                'id': ann_id,
                'image_id': 1,
                'category_id': self.category_to_id[label],
                'bbox': bbox,
                'area': area,
                'iscrowd': 0,
                'segmentation': [],
            })
            ann_id += 1

        return {
            'images': images,
            'annotations': annotations,
            'categories': categories,
        }

    def save(self, target_file: str, shapes: List[Dict[str, Any]]):
        data = self.build(shapes)
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)



class CocoReader:

    def __init__(self, json_path: str):
        self.json_path = json_path
        self.shapes: List[Tuple[str, List[Tuple[int, int]], Optional[Tuple[int,int,int,int]], Optional[Tuple[int,int,int,int]], bool]] = []
        self.verified = False
        self._data: Dict[str, Any] = {}
        self._categories: Dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._data = data
        # Build category id -> name map
        categories = data.get('categories', [])
        self._categories = {int(cat['id']): cat['name'] for cat in categories if 'id' in cat and 'name' in cat}
        # Only first image is used in this single-image loader pattern
        images = data.get('images', [])
        if not images:
            return
        image_id = images[0].get('id', 1)
        anns = [a for a in data.get('annotations', []) if a.get('image_id') == image_id]
        for ann in anns:
            cat_id = int(ann.get('category_id', 0))
            label = self._categories.get(cat_id, '')
            bbox = ann.get('bbox', None)
            if not label or not bbox or len(bbox) != 4:
                continue
            x, y, w, h = bbox
            # Convert to Pascal-like 4 points rectangle
            x_min = int(round(x))
            y_min = int(round(y))
            x_max = int(round(x + w))
            y_max = int(round(y + h))
            points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
            self.shapes.append((label, points, None, None, False))

    def get_shapes(self) -> list:
        return self.shapes

