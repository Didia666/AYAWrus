import os
import time
from thrember.features import PEFeatureExtractor

extractor = PEFeatureExtractor()

# Put paths to a few of your slowest .exe files here
TEST_FILES = [
    r"C:\Users\PLPASIG\Downloads\Packet_Tracer822_64bit_setup_signed.exe",
    r"C:\Users\PLPASIG\Downloads\StarRail_setup_ua_2b187a7bfa93.exe",
    r"C:\Users\PLPASIG\Downloads\TRAE_SOLO-Setup-x64.exe",
]

for file_path in TEST_FILES:
    if not os.path.exists(file_path):
        print(f"Skipping missing file: {file_path}")
        continue

    t0 = time.perf_counter()
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    t1 = time.perf_counter()

    try:
        features = extractor.feature_vector(file_bytes)
        t2 = time.perf_counter()
        print(f"{os.path.basename(file_path)}: "
              f"read={t1-t0:.2f}s, extract={t2-t1:.2f}s, "
              f"size={len(file_bytes)/1e6:.1f}MB")
    except Exception as e:
        print(f"{os.path.basename(file_path)}: extraction failed: {e}")