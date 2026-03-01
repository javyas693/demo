from __future__ import annotations

from typing import Dict, Iterable, List, Tuple, Sequence

def weights_array_to_tuple(weights: Sequence[float], assets: Iterable[str]) -> Tuple[float, ...]:
    """
    Convert an array/sequence of weights into an immutable tuple.
    Validates length matches assets length.
    """
    assets_list = list(assets)
    if len(weights) != len(assets_list):
        raise ValueError(f"weights length {len(weights)} does not match assets length {len(assets_list)}")
    return tuple(float(x) for x in weights)


def weights_tuple_to_dict(weights: Tuple[float, ...], assets: Iterable[str]) -> Dict[str, float]:
    assets_list = list(assets)
    if len(weights) != len(assets_list):
        raise ValueError(f"weights length {len(weights)} does not match assets length {len(assets_list)}")
    return {sym: float(w) for sym, w in zip(assets_list, weights)}