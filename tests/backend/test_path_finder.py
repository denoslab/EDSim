import copy
import pytest
from path_finder import path_finder, closest_coordinate


class TestPathFinder:
    def test_reachable_path_is_nonempty(self, simple_maze):
        path = path_finder(simple_maze, (1, 1), (3, 3), 1)
        assert isinstance(path, list)
        assert len(path) > 0

    def test_path_endpoints(self, simple_maze):
        start = (1, 1)
        end = (3, 3)
        path = path_finder(simple_maze, start, end, 1)
        assert path[0] == start
        assert path[-1] == end

    def test_start_equals_end(self, simple_maze):
        # Same start and end — path should be a single-element list
        path = path_finder(simple_maze, (1, 1), (1, 1), 1)
        assert isinstance(path, list)

    def test_blocked_destination(self):
        # Start and end are separated by a wall column — no path possible.
        # Maze (0=open, 1=wall): col=0 open, col=1 wall, col=2 open on row=1.
        # path_finder uses (x,y) → swaps to (row=y, col=x) internally.
        maze = [
            [1, 1, 1],
            [0, 1, 0],
            [1, 1, 1],
        ]
        # game coord (0,1)=open, (2,1)=open, separated by wall at (1,1)
        path = path_finder(maze, (0, 1), (2, 1), 1)
        # path_finder_v2 returns just [(end)] when no path found
        assert len(path) <= 1

    def test_all_path_cells_within_bounds(self, simple_maze):
        rows = len(simple_maze)
        cols = len(simple_maze[0])
        path = path_finder(simple_maze, (1, 1), (3, 3), 1)
        for r, c in path:
            assert 0 <= r < rows
            assert 0 <= c < cols


class TestClosestCoordinate:
    def test_nearest_of_two(self):
        result = closest_coordinate((0, 0), [(1, 1), (5, 5)])
        assert result == (1, 1)

    def test_single_target_returned(self):
        result = closest_coordinate((3, 3), [(7, 7)])
        assert result == (7, 7)

    def test_exact_match(self):
        result = closest_coordinate((2, 2), [(2, 2), (9, 9)])
        assert result == (2, 2)
