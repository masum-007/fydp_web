"""Decision semantics shared by inference and dependency-free tests."""
import math


def classify(probability, threshold):
    probability, threshold = float(probability), float(threshold)
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError('Model returned an invalid fake probability.')
    if not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError('Decision threshold must be strictly between 0 and 1.')
    fake = probability >= threshold
    return {'prediction': 'Fake' if fake else 'Real',
            'fake_probability': probability, 'real_probability': 1 - probability,
            'confidence': probability if fake else 1 - probability,
            'threshold': threshold}
