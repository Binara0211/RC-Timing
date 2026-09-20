import cv2
import numpy as np
import pytest


@pytest.mark.parametrize("marker_id", range(1, 8))
def test_all_car_markers_detect_after_rotation(marker_id):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 300)
    canvas = np.full((520, 520), 255, np.uint8)
    canvas[110:410, 110:410] = marker
    M = cv2.getRotationMatrix2D((260, 260), 17, 1.0)
    rotated = cv2.warpAffine(canvas, M, (520, 520), borderValue=255)
    _corners, ids, _rej = detector.detectMarkers(rotated)
    assert ids is not None
    assert marker_id in [int(x[0]) for x in ids]
