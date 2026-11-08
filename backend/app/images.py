import io
import warnings
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException

MAX_PIXELS = 20_000_000
FORMATS = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}


def inspect_image(data: bytes):
    if not data:
        raise HTTPException(422, 'The image is empty.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in FORMATS:
                    raise HTTPException(415, 'Only JPEG, PNG and WEBP are supported.')
                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(413, 'Image exceeds 20 million pixels.')
                if getattr(image, 'n_frames', 1) != 1:
                    raise HTTPException(415, 'Animated images are not supported.')
                result = (image.width, image.height, FORMATS[image.format])
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
            return result
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(413, 'Image dimensions are too large.')
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise HTTPException(422, 'Invalid or corrupted image.')
