from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "markers"
OUT.mkdir(parents=True, exist_ok=True)
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
for marker_id in range(1, 8):
    img = cv2.aruco.generateImageMarker(dictionary, marker_id, 1000)
    cv2.imwrite(str(OUT / f"marker_{marker_id}.png"), img)
print(f"Generated 7 markers in {OUT}")
