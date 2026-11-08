"""Notebook-derived model adapter; only trusted administrator-provided artifacts are loaded."""
import io
import json
import logging
import math
from pathlib import Path
from threading import Lock

from .manifest import load_manifest, sha256_file
from .prediction import classify

logger = logging.getLogger(__name__)


class InferenceEngine:
    def __init__(self, manifest_path):
        self.path = Path(manifest_path)
        self.ready = False
        self.reason = 'MODEL_NOT_CONFIGURED'
        self.models = {}
        self.lock = Lock()

    def load(self):
        if not self.path.is_file():
            return
        try:
            self.manifest = load_manifest(self.path)
            import tensorflow as tf
            import numpy as np
            from PIL import Image
            from matplotlib import colormaps
            self.tf, self.np, self.Image, self.colormaps = tf, np, Image, colormaps
            for member in self.manifest['members']:
                model = tf.keras.models.load_model(self.path.parent / member['file'], compile=False, safe_mode=True)
                if tuple(model.input_shape) != (None, 224, 224, 3) or tuple(model.output_shape) != (None, 1):
                    raise ValueError('Unexpected model input/output shape.')
                if model.name != member['name'] + '_deepfake_detector':
                    raise ValueError('Model name does not match artifact manifest.')
                preprocess = model.get_layer('preprocess')
                if not isinstance(preprocess, tf.keras.layers.Rescaling):
                    raise ValueError('Expected embedded Rescaling preprocessing.')
                config = preprocess.get_config()
                if not math.isclose(float(config['scale']), 1 / 127.5) or float(config['offset']) != -1:
                    raise ValueError('Unexpected embedded rescaling.')
                if model.get_layer('classifier').get_config()['activation'] != 'sigmoid':
                    raise ValueError('Expected sigmoid Fake probability output.')
                self.models[member['name']] = model
            self.model_version = sha256_file(self.path)
            # Exercise both model output and explanation graph before readiness becomes true.
            probe = tf.zeros((1, 224, 224, 3), tf.float32)
            for member in self.manifest['members']:
                self._probability(self.models[member['name']], probe)
            self._gradcam(probe, self.manifest['explanation_model'], 1)
            self.reason = None
            self.ready = True
        except Exception:
            logger.exception('Model startup validation failed; inference remains unavailable.')
            self.models = {}
            self.reason = 'MODEL_LOAD_FAILED'
            self.ready = False

    def _probability(self, model, batch):
        value = self.np.asarray(model(batch, training=False))
        if value.shape != (1, 1):
            raise ValueError('Unexpected prediction shape.')
        probability = float(value[0, 0])
        classify(probability, 0.5)  # validates finite range, not the deployment decision
        return probability

    def _prepare(self, data):
        tf, np = self.tf, self.np
        with self.Image.open(io.BytesIO(data)) as image:
            if image.format not in {'JPEG', 'PNG'}:
                raise ValueError('Stage 2 inference supports JPEG/PNG only to match the validation decoder.')
        image = tf.io.decode_image(data, channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        original = np.asarray(image, dtype=np.uint8)
        resized = tf.image.resize(image, (224, 224), method='bilinear', antialias=True)
        # Embedded preprocess layer performs the only normalization.
        batch = tf.ensure_shape(tf.cast(resized, tf.float32), [224, 224, 3])[None, ...]
        return original, batch

    def _gradcam(self, batch, name, target):
        tf, np = self.tf, self.np
        model = self.models[name]
        backbone = next(layer for layer in model.layers
                        if isinstance(layer, tf.keras.Model) and len(layer.output.shape) == 4)
        spatial = next(layer for layer in reversed(backbone.layers) if len(layer.output.shape) == 4)
        features = tf.keras.Model(backbone.input, [spatial.output, backbone.output])
        with tf.GradientTape() as tape:
            # Watch input explicitly so entirely frozen backbones remain differentiable.
            tape.watch(batch)
            x = model.get_layer('preprocess')(batch)
            conv, final_features = features(x, training=False)
            x = model.get_layer('gap')(final_features)
            x = model.get_layer('head_bn')(x, training=False)
            x = model.get_layer('head_dense')(x)
            x = model.get_layer('dropout')(x, training=False)
            fake_probability = model.get_layer('classifier')(x)[:, 0]
            score = fake_probability if target == 1 else 1 - fake_probability
        gradients = tape.gradient(score, conv)
        if gradients is None:
            raise ValueError('Grad-CAM graph is disconnected.')
        gradients, conv = tf.cast(gradients, tf.float32), tf.cast(conv, tf.float32)
        weights = tf.reduce_mean(gradients, axis=(1, 2))
        heatmap = tf.nn.relu(tf.reduce_sum(conv * weights[:, None, None, :], axis=-1))[0]
        heatmap = tf.math.divide_no_nan(heatmap, tf.reduce_max(heatmap))
        result = heatmap.numpy()
        if not np.isfinite(result).all():
            raise ValueError('Non-finite Grad-CAM map.')
        return result, spatial.name

    def predict(self, data):
        if not self.ready:
            raise RuntimeError('Model not ready.')
        with self.lock:
            original, batch = self._prepare(data)
            members = {member['name']: classify(self._probability(self.models[member['name']], batch), member['threshold'])
                       for member in self.manifest['members']}
            if self.manifest['mode'] == 'ensemble':
                probability = sum(member['fake_probability'] for member in members.values()) / len(members)
            else:
                probability = members[self.manifest['model']]['fake_probability']
            decision = classify(probability, self.manifest['threshold'])
            explanation_name = self.manifest['explanation_model']
            explanation_decision = members[explanation_name]
            target = int(explanation_decision['prediction'] == 'Fake')
            heatmap, layer = self._gradcam(batch, explanation_name, target)
            # Render on the same RGB decode/orientation used for inference; originals stay untouched.
            small = self.Image.fromarray((self.np.clip(heatmap, 0, 1) * 255).astype('uint8'))
            full = self.np.asarray(small.resize((original.shape[1], original.shape[0]), self.Image.Resampling.BILINEAR)) / 255.0
            color = self.colormaps['jet'](full)[..., :3] * 255
            overlay = self.np.clip(0.62 * original.astype('float32') + 0.38 * color, 0, 255).astype('uint8')
            assets = {}
            for name, array in [('heatmap', color.astype('uint8')), ('overlay', overlay)]:
                buffer = io.BytesIO()
                self.Image.fromarray(array).save(buffer, format='PNG')
                assets[name] = buffer.getvalue()
            result = {**decision, 'model': self.manifest['model'], 'mode': self.manifest['mode'],
                      'model_version': self.model_version,
                      'model_artifacts': [{k: member[k] for k in ('name', 'sha256')} for member in self.manifest['members']],
                      'preprocessing': self.manifest['preprocessing'], 'members': members,
                      'explanation': {'method': 'Grad-CAM', 'model': explanation_name,
                                      'target_label': explanation_decision['prediction'],
                                      'threshold': explanation_decision['threshold'],
                                      'fake_probability': explanation_decision['fake_probability'],
                                      'layer': layer, 'weak_activation': bool(heatmap.max() <= 0),
                                      'scope': 'single_model',
                                      'note': 'Explains the named single model; not an ensemble explanation or proof of manipulation.'}}
            return result, assets
