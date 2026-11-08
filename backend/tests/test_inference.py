"""Synthetic graph checks only; these do not validate the user's trained weights."""
import io
import json
import math
import pytest

tf = pytest.importorskip('tensorflow')
np = pytest.importorskip('numpy')
from PIL import Image
from app.inference import InferenceEngine
from app.manifest import PREPROCESSING, sha256_file


@pytest.mark.parametrize('mode', ['single', 'ensemble'])
def test_frozen_backbone_and_embedded_preprocessing(tmp_path, mode):
    names = ['ResNet50V2'] if mode == 'single' else ['MobileNetV2', 'ResNet50V2', 'Xception']
    members = []
    for name in names:
        backbone_input = tf.keras.Input((224, 224, 3))
        features = tf.keras.layers.Conv2D(2, 3, strides=32, name='spatial')(backbone_input)
        backbone = tf.keras.Model(backbone_input, features)
        backbone.trainable = False
        inputs = tf.keras.Input((224, 224, 3))
        x = tf.keras.layers.Rescaling(1 / 127.5, offset=-1, name='preprocess')(inputs)
        x = backbone(x, training=False)
        x = tf.keras.layers.GlobalAveragePooling2D(name='gap')(x)
        x = tf.keras.layers.BatchNormalization(name='head_bn')(x)
        x = tf.keras.layers.Dense(4, activation='swish', name='head_dense')(x)
        x = tf.keras.layers.Dropout(.35, name='dropout')(x)
        out = tf.keras.layers.Dense(1, activation='sigmoid', kernel_initializer='zeros',
                                   bias_initializer=tf.keras.initializers.Constant(math.log(.4 / .6)),
                                   name='classifier')(x)
        model = tf.keras.Model(inputs, out, name=name + '_deepfake_detector')
        path = tmp_path / (name + '.keras')
        model.save(path)
        members.append({'name': name, 'file': path.name, 'sha256': sha256_file(path), 'threshold': .375})
    manifest = {'schema_version': 1, 'preprocessing': PREPROCESSING, 'image_size': [224, 224],
                'class_mapping': {'0': 'Real', '1': 'Fake'}, 'members': members, 'mode': mode,
                'model': 'ResNet50V2' if mode == 'single' else 'Ensemble',
                'threshold': .375 if mode == 'single' else .565, 'explanation_model': 'ResNet50V2'}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    engine = InferenceEngine(path)
    engine.load()
    assert engine.ready
    stream = io.BytesIO()
    Image.new('RGB', (30, 25), 'white').save(stream, format='PNG')
    original, batch = engine._prepare(stream.getvalue())
    assert original.shape == (25, 30, 3)
    assert tuple(batch.shape) == (1, 224, 224, 3)
    np.testing.assert_allclose(batch.numpy(), 255, atol=1e-3)
    result, assets = engine.predict(stream.getvalue())
    assert result['fake_probability'] == pytest.approx(.4, abs=1e-5)
    assert result['prediction'] == ('Fake' if mode == 'single' else 'Real')
    assert result['explanation']['target_label'] == 'Fake'
    assert result['explanation']['scope'] == 'single_model'
    assert set(assets) == {'heatmap', 'overlay'}
    assert result['explanation']['weak_activation']
