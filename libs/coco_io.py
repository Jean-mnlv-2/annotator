#!/usr/bin/env python
# -*- coding: utf8 -*-
import json
from typing import List, Dict, Any, Tuple


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


