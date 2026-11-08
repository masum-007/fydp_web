"""Package existing Kaggle outputs without retraining or loading TensorFlow."""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.manifest import NAMES, PREPROCESSING, sha256_file, load_manifest


def prepare(source, destination, mode):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    metadata = json.loads((source / 'deployment_metadata.json').read_text(encoding='utf-8'))
    if metadata['image_size'] != [224, 224] or metadata['class_mapping'] != {'0': 'Real', '1': 'Fake'}:
        raise ValueError('Export does not match this notebook contract.')
    selected = metadata['deployed_model']
    if selected not in NAMES:
        raise ValueError('Unknown deployed model.')
    thresholds = {selected: float(metadata['decision_threshold'])}
    if mode == 'ensemble':
        with (source / 'reports' / 'validation_all_candidates.csv').open(newline='', encoding='utf-8') as file:
            thresholds.update({row['model']: float(row['threshold']) for row in csv.DictReader(file)})
        names = ['MobileNetV2', 'ResNet50V2', 'Xception']
        model_name = 'Ensemble'
    else:
        names, model_name = [selected], selected
    # Resolve every required file before writing anything.
    paths = {name: source / 'models' / f'{name}_best.keras' for name in names}
    if mode == 'single' and not paths[selected].is_file():
        paths[selected] = source / 'deepfake_detector_best_single.keras'
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        if name not in thresholds:
            raise ValueError('Missing validation threshold for ' + name)
    if model_name not in thresholds:
        raise ValueError('Missing final model threshold.')
    destination.mkdir(parents=True, exist_ok=True)
    members = []
    for name, source_path in paths.items():
        target = destination / f'{name}_best.keras'
        if source_path != target:
            shutil.copy2(source_path, target)
        members.append({'name': name, 'file': target.name, 'sha256': sha256_file(target), 'threshold': thresholds[name]})
    manifest = {'schema_version': 1, 'mode': mode, 'model': model_name,
                'threshold': thresholds[model_name], 'explanation_model': selected,
                'class_mapping': {'0': 'Real', '1': 'Fake'}, 'image_size': [224, 224],
                'preprocessing': PREPROCESSING, 'members': members,
                'source': 'deepfake-v1.ipynb export; threshold values read from export metadata/CSV'}
    manifest_path = destination / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    load_manifest(manifest_path)
    print('Prepared:', manifest_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', help='Extracted deepfake_xai_outputs directory containing deployment_metadata.json')
    parser.add_argument('--destination', default='artifacts')
    parser.add_argument('--mode', choices=['single', 'ensemble'], default='single')
    args = parser.parse_args()
    prepare(args.source, args.destination, args.mode)
