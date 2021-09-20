import sys
import os
import pytest

src_dir = os.path.join(os.path.dirname(__file__), "..")
files_dir = os.path.join(src_dir, "files")
sys.path.append(files_dir)
import monitor_runs as mr


@pytest.mark.parametrize("example,result", [("1.0", 1.0), ("2.5", 2.5), ("4", 4), ("string", "string"), ("24h", "24h"), (1, 1), (2.4, 2.4), (0.0, 0.0), (0, 0), (None, None),
                                            (-42, -42), (-4.5, -4.5), ({"foo": "bar"}, {"foo": "bar"}), ({"set"}, {"set"}), ({3}, {3}), ([3], [3]), ((3, 6), (3, 6))])
def test_transform_to_number(example, result):
    transformation = mr._transform_to_number(example)
    assert transformation == result
    assert type(transformation) == type(result)


@pytest.mark.parametrize("example,result", [({"a": "1.0", "b": "2.5", "c": 2.5, "d": "string", "e": "24h"}, {"a": 1.0, "b": 2.5, "c": 2.5, "d": "string", "e": "24h"}), ({}, {})])
def test_translate_integers(example, result):
    transformation = mr._translate_integers(example)
    assert len(transformation) == len(result)
    for key in transformation:
        assert transformation[key] == result[key]
        assert isinstance(transformation[key], type(result[key]))
