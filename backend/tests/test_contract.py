"""Run without external packages: python -m unittest discover -s tests -p test_contract.py"""
import json
import tempfile
import unittest
from pathlib import Path
from app.manifest import PREPROCESSING, load_manifest, sha256_file
from app.prediction import classify
from tools.prepare_artifacts import prepare


class ContractTests(unittest.TestCase):
    def test_threshold_equality(self):
        self.assertEqual(classify(.565, .565)['prediction'], 'Fake')
        self.assertEqual(classify(.564, .565)['prediction'], 'Real')

    def test_confidence_is_predicted_class_score(self):
        self.assertEqual(classify(.4, .375)['prediction'], 'Fake')
        self.assertEqual(classify(.4, .375)['confidence'], .4)
        self.assertAlmostEqual(classify(.55, .565)['confidence'], .45)

    def test_invalid_probabilities(self):
        for p in [float('nan'), float('inf'), -0.1, 1.1]:
            with self.assertRaises(ValueError):
                classify(p, .565)

    def test_invalid_thresholds(self):
        for t in [0, 1, float('nan')]:
            with self.assertRaises(ValueError):
                classify(.5, t)

    def test_single_export_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'deepfake_detector_best_single.keras').write_bytes(b'contract fixture; not an actual model')
            (source / 'deployment_metadata.json').write_text(json.dumps({
                'image_size': [224, 224], 'class_mapping': {'0': 'Real', '1': 'Fake'},
                'deployed_model': 'ResNet50V2', 'decision_threshold': .375}))
            destination = root / 'artifacts'
            prepare(source, destination, 'single')
            manifest = load_manifest(destination / 'manifest.json')
            self.assertEqual(manifest['threshold'], .375)
            self.assertEqual(manifest['model'], 'ResNet50V2')
            self.assertEqual(manifest['preprocessing'], PREPROCESSING)
            (destination / 'ResNet50V2_best.keras').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                load_manifest(destination / 'manifest.json')

    def test_ensemble_export_uses_validation_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            (source / 'models').mkdir(parents=True)
            (source / 'reports').mkdir()
            for name in ['MobileNetV2', 'ResNet50V2', 'Xception']:
                (source / 'models' / (name + '_best.keras')).write_bytes(name.encode())
            (source / 'deployment_metadata.json').write_text(json.dumps({
                'image_size': [224, 224], 'class_mapping': {'0': 'Real', '1': 'Fake'},
                'deployed_model': 'ResNet50V2', 'decision_threshold': .375}))
            (source / 'reports' / 'validation_all_candidates.csv').write_text(
                'model,threshold\nMobileNetV2,0.205\nResNet50V2,0.375\nXception,0.505\nEnsemble,0.565\n')
            destination = root / 'artifacts'
            prepare(source, destination, 'ensemble')
            path = destination / 'manifest.json'
            m = load_manifest(path)
            self.assertEqual(m['threshold'], .565)
            self.assertEqual(len(m['members']), 3)
            m['members'][0]['file'] = '../source/models/MobileNetV2_best.keras'
            path.write_text(json.dumps(m))
            with self.assertRaises(ValueError):
                load_manifest(path)


if __name__ == '__main__':
    unittest.main()
