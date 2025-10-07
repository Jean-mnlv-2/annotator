import os
import sys
import unittest


class TestYoloRW(unittest.TestCase):

    def setUp(self):
        self.dir_name = os.path.abspath(os.path.dirname(__file__))
        libs_path = os.path.join(self.dir_name, '..', 'libs')
        sys.path.insert(0, libs_path)
        from yolo_io import YOLOWriter, YoloReader
        from PyQt5.QtGui import QImage  # ensure Qt available for reader img size
        self.YOLOWriter = YOLOWriter
        self.YoloReader = YoloReader
        # Fake image path used by writer filename
        self.img_file = 'tests/test.512.512.bmp'
        self.out_txt = os.path.join(self.dir_name, 'yolo_test.txt')
        self.classes_file = os.path.join(self.dir_name, 'classes.txt')

    def tearDown(self):
        for path in [self.out_txt, self.classes_file]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def test_yolo_roundtrip(self):
        # Write
        writer = self.YOLOWriter('tests', os.path.basename(self.img_file), (512, 512, 1), local_img_path=self.img_file)
        writer.add_bnd_box(60, 40, 430, 504, 'person', 0)
        writer.add_bnd_box(113, 40, 450, 403, 'face', 0)
        writer.save(target_file=self.out_txt, class_list=['person', 'face'])

        # Read back
        from PyQt5.QtGui import QImage
        image = QImage(os.path.join(self.dir_name, 'test.512.512.bmp'))
        reader = self.YoloReader(self.out_txt, image, class_list_path=self.classes_file)
        shapes = reader.get_shapes()

        self.assertEqual(2, len(shapes), 'shape count mismatch')
        labels = [s[0] for s in shapes]
        self.assertIn('person', labels)
        self.assertIn('face', labels)


if __name__ == '__main__':
    unittest.main()


