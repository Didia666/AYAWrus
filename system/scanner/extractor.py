from thrember.features import PEFeatureExtractor

_extractor = None

def get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = PEFeatureExtractor()
    return _extractor