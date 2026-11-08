"""Deployment contract. No TensorFlow import is needed to validate it."""
import hashlib
import json
import math
from pathlib import Path

NAMES = {'MobileNetV2', 'ResNet50V2', 'Xception'}
PREPROCESSING = 'tf_decode_rgb_resize_bilinear_antialias_224_raw_0_255_v1'


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('preprocessing') != PREPROCESSING:
        raise ValueError('Unsupported manifest schema or preprocessing contract.')
    if data.get('image_size') != [224, 224] or data.get('class_mapping') != {'0': 'Real', '1': 'Fake'}:
        raise ValueError('Unexpected input shape or class mapping.')
    members = data.get('members', [])
    names = [m['name'] for m in members]
    if len(names) != len(set(names)) or not set(names) <= NAMES:
        raise ValueError('Unexpected or duplicate model members.')
    if data.get('mode') == 'ensemble':
        if set(names) != NAMES or data.get('model') != 'Ensemble':
            raise ValueError('Ensemble requires all three trained models.')
    elif data.get('mode') == 'single':
        if len(names) != 1 or data.get('model') != names[0]:
            raise ValueError('Single-model manifest must contain exactly its named model.')
    else:
        raise ValueError('mode must be single or ensemble.')
    if data.get('explanation_model') not in names:
        raise ValueError('Explanation model must be an available member.')
    for value in [data['threshold'], *(m['threshold'] for m in members)]:
        if isinstance(value, bool) or not math.isfinite(float(value)) or not 0 < float(value) < 1:
            raise ValueError('Invalid decision threshold.')
    if data['mode'] == 'single' and float(data['threshold']) != float(members[0]['threshold']):
        raise ValueError('Single-model threshold mismatch.')
    for member in members:
        model_path = (path.parent / member['file']).resolve()
        if not model_path.is_relative_to(path.parent) or model_path.suffix != '.keras':
            raise ValueError('Model must be a .keras file inside the artifact directory.')
        if sha256_file(model_path) != member['sha256']:
            raise ValueError('Model checksum mismatch: ' + member['name'])
    return data
