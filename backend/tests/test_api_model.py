"""Tests for player-chosen / API models.

Run from the backend/ directory:  py tests\test_api_model.py
The router stays local-first, but when an API model is configured it is used for
the chosen tiers (with graceful fallback to Ollama/stub on any error).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["REALMWEAVE_FORCE_STUB"] = "1"

from realmweave.config import load_config
from realmweave.llm.router import LLMRouter, LLMRequest, Tier
from realmweave.llm.api_backend import make_api_backend


class TestApiBackendFactory(unittest.TestCase):
    def test_disabled_returns_none(self):
        self.assertIsNone(make_api_backend(None))
        self.assertIsNone(make_api_backend({"enabled": False}))

    def test_enabled_without_key_or_model_returns_none(self):
        # enabled but no model, and the key env var is unset
        os.environ.pop("REALMWEAVE_TEST_KEY", None)
        cfg = {"enabled": True, "provider": "anthropic", "model": "",
               "api_key_env": "REALMWEAVE_TEST_KEY"}
        self.assertIsNone(make_api_backend(cfg))
        cfg["model"] = "claude-x"
        self.assertIsNone(make_api_backend(cfg), "no key -> no backend")


class TestRouterUsesApi(unittest.TestCase):
    def test_configured_tier_routes_to_api(self):
        cfg = load_config(); cfg["force_stub"] = True
        router = LLMRouter(cfg)
        calls = {}

        def fake_api(req, model):
            calls["used"] = True
            return "The gods have spoken through the cloud."
        router.set_api_backend(fake_api)

        # a high-importance (narrative) request should use the API backend
        resp = router.generate(LLMRequest(prompt="a death occurs", importance=9.0))
        self.assertEqual(resp.backend, "api")
        self.assertIn("cloud", resp.text)
        self.assertTrue(calls.get("used"))

    def test_low_tier_stays_local_by_default(self):
        cfg = load_config(); cfg["force_stub"] = True
        router = LLMRouter(cfg)
        router.set_api_backend(lambda req, model: "SHOULD NOT BE USED")
        # ambient chatter (reflex tier) is not in api_tiers -> stays on stub
        resp = router.generate(LLMRequest(prompt="hello there", importance=1.0))
        self.assertEqual(resp.backend, "stub")

    def test_api_tiers_can_be_widened(self):
        cfg = load_config(); cfg["force_stub"] = True
        router = LLMRouter(cfg)
        router.api_tiers = {"reflex", "dialogue", "narrative"}
        router.set_api_backend(lambda req, model: "cloud reply")
        resp = router.generate(LLMRequest(prompt="chat", importance=1.0))  # reflex
        self.assertEqual(resp.backend, "api")

    def test_api_failure_falls_back(self):
        cfg = load_config(); cfg["force_stub"] = True
        router = LLMRouter(cfg)

        def boom(req, model):
            raise RuntimeError("api down")
        router.set_api_backend(boom)
        resp = router.generate(LLMRequest(prompt="a death occurs", importance=9.0))
        self.assertEqual(resp.backend, "stub")   # gracefully fell back


if __name__ == "__main__":
    unittest.main(verbosity=2)
