import json
import os
import pytest
from django.test import Client, TestCase


@pytest.fixture
def client():
    return Client()


class TestLandingView(TestCase):
    def test_landing_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class TestPathTesterView(TestCase):
    def test_path_tester_returns_200(self):
        response = self.client.get("/path_tester/")
        self.assertEqual(response.status_code, 200)


class TestGetSimOutput(TestCase):
    def test_returns_empty_outputs_when_file_absent(self, tmp_path=None):
        # The view reads from temp_storage/sim_output.json relative to CWD.
        # When the file doesn't exist it should return {"outputs": []}.
        response = self.client.get("/get_sim_output/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("outputs", data)
        self.assertEqual(data["outputs"], [])


class TestSendSimCommand(TestCase):
    def test_valid_command_returns_ok(self):
        response = self.client.post(
            "/send_sim_command/",
            data=json.dumps({"command": "run 10"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get("ok"))
        self.assertIn("id", data)

    def test_missing_command_returns_400(self):
        response = self.client.post(
            "/send_sim_command/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data.get("ok"))
