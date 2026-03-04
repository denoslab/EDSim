import os
import pytest
from global_methods import average, std, array_to_2d, create_folder_if_not_there


class TestAverage:
    def test_basic(self):
        assert average([1, 2, 3]) == 2.0

    def test_single_element(self):
        assert average([5]) == 5.0

    def test_floats(self):
        assert average([0.5, 1.5]) == 1.0


class TestStd:
    def test_zero_variance(self):
        assert std([4, 4, 4]) == 0.0

    def test_known_value(self):
        # population std of [2,4,4,4,5,5,7,9] == 2.0
        assert abs(std([2, 4, 4, 4, 5, 5, 7, 9]) - 2.0) < 1e-9


class TestArrayTo2D:
    def test_shape(self):
        layer = {"data": list(range(6))}
        result = array_to_2d(layer, height=2, width=3)
        assert len(result) == 2
        assert all(len(row) == 3 for row in result)

    def test_values(self):
        layer = {"data": [10, 20, 30, 40]}
        result = array_to_2d(layer, height=2, width=2)
        assert result[0] == [10, 20]
        assert result[1] == [30, 40]


class TestCreateFolderIfNotThere:
    def test_creates_new_folder(self, tmp_path):
        new_dir = str(tmp_path / "new_folder" / "sub")
        result = create_folder_if_not_there(new_dir + "/file.txt")
        assert result is True
        assert os.path.isdir(new_dir)

    def test_idempotent_existing_folder(self, tmp_path):
        existing = str(tmp_path / "exists")
        os.makedirs(existing)
        result = create_folder_if_not_there(existing + "/file.txt")
        assert result is False
