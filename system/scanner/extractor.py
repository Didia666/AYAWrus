import numpy as _np
import functools as _functools

_original_hstack = _np.hstack
_original_vstack = _np.vstack

@_functools.wraps(_original_hstack)
def _compat_hstack(tup, *args, **kwargs):
    dtype = kwargs.pop("dtype", None)
    casting = kwargs.pop("casting", "same_kind")
    result = _original_hstack(tup, *args, **kwargs)
    if dtype is not None:
        result = result.astype(dtype, casting=casting)
    return result

@_functools.wraps(_original_vstack)
def _compat_vstack(tup, *args, **kwargs):
    dtype = kwargs.pop("dtype", None)
    casting = kwargs.pop("casting", "same_kind")
    result = _original_vstack(tup, *args, **kwargs)
    if dtype is not None:
        result = result.astype(dtype, casting=casting)
    return result

_np.hstack = _compat_hstack
_np.vstack = _compat_vstack

from thrember.features import PEFeatureExtractor

_extractor = None

def get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = PEFeatureExtractor()
    return _extractor