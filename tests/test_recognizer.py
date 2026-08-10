import numpy as np

from manager_rifiuti.recognizer import rectify


def test_rectify_rotates_portrait_image():
    image = np.full((300, 180, 3), 255, dtype=np.uint8)
    corrected = rectify(image)
    assert corrected.shape[1] > corrected.shape[0]


def test_rectify_keeps_landscape_image():
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    corrected = rectify(image)
    assert corrected.shape == image.shape
