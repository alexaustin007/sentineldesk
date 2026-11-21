"""Tests for the classification inference module."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "classification"))

from classification.classify import classify_ticket, detect_language


class TestDetectLanguage(unittest.TestCase):
    def test_english(self) -> None:
        self.assertEqual(detect_language("I cannot connect to the VPN"), "en")

    def test_german(self) -> None:
        self.assertEqual(
            detect_language("Ich kann mich nicht mit dem VPN verbinden"), "de"
        )

    def test_fallback_on_empty(self) -> None:
        result = detect_language("")
        self.assertIn(result, ("en", "de"))


class TestClassifyTicket(unittest.TestCase):
    """Test classify_ticket with mock pipelines to avoid needing trained models."""

    def _make_mock_pipeline(self, classes: list[str], proba: list[float]):
        """Return an object that quacks like a fitted sklearn pipeline."""
        import numpy as np

        class FakePipeline:
            classes_ = np.array(classes)

            def predict_proba(self, X):
                return np.array([proba])

        return FakePipeline()

    def test_output_schema(self) -> None:
        pipelines = {
            "type": self._make_mock_pipeline(
                ["Change", "Incident", "Problem", "Request"],
                [0.05, 0.80, 0.10, 0.05],
            ),
            "queue": self._make_mock_pipeline(
                ["Technical Support", "Product Support"],
                [0.90, 0.10],
            ),
            "priority": self._make_mock_pipeline(
                ["high", "low", "medium"],
                [0.70, 0.10, 0.20],
            ),
        }

        result = classify_ticket(
            subject="VPN down",
            body="Cannot connect to corporate VPN from multiple locations",
            pipelines=pipelines,
        )

        self.assertEqual(result["predicted_type"], "Incident")
        self.assertEqual(result["predicted_queue"], "Technical Support")
        self.assertEqual(result["predicted_priority"], "high")

        self.assertIn("confidence", result)
        self.assertIn("type", result["confidence"])
        self.assertIn("queue", result["confidence"])
        self.assertIn("priority", result["confidence"])

        self.assertIn("classification_margin", result)
        self.assertIn("escalation", result)
        self.assertIn("required", result["escalation"])
        self.assertIn("reasons", result["escalation"])
        self.assertIn("detected_language", result)
        self.assertIn("inference_latency_ms", result)

    def test_escalation_on_critical_incident(self) -> None:
        pipelines = {
            "type": self._make_mock_pipeline(
                ["Change", "Incident", "Problem", "Request"],
                [0.02, 0.90, 0.05, 0.03],
            ),
            "queue": self._make_mock_pipeline(["Technical Support"], [1.0]),
            "priority": self._make_mock_pipeline(
                ["high", "low", "medium"],
                [0.85, 0.05, 0.10],
            ),
        }

        result = classify_ticket(
            subject="System outage",
            body="All production servers are down affecting all customers",
            pipelines=pipelines,
        )

        self.assertTrue(result["escalation"]["required"])
        self.assertTrue(any("Incident" in r for r in result["escalation"]["reasons"]))

    def test_no_escalation_on_routine_ticket(self) -> None:
        pipelines = {
            "type": self._make_mock_pipeline(
                ["Change", "Incident", "Problem", "Request"],
                [0.02, 0.03, 0.05, 0.90],
            ),
            "queue": self._make_mock_pipeline(
                ["Billing and Payments", "Technical Support"],
                [0.85, 0.15],
            ),
            "priority": self._make_mock_pipeline(
                ["high", "low", "medium"],
                [0.05, 0.85, 0.10],
            ),
        }

        result = classify_ticket(
            subject="Password reset",
            body="I need to reset my password for the billing portal please",
            pipelines=pipelines,
        )

        self.assertFalse(result["escalation"]["required"])

    def test_escalation_on_low_confidence(self) -> None:
        pipelines = {
            "type": self._make_mock_pipeline(
                ["Change", "Incident", "Problem", "Request"],
                [0.30, 0.35, 0.20, 0.15],
            ),
            "queue": self._make_mock_pipeline(
                ["Technical Support", "Product Support"],
                [0.55, 0.45],
            ),
            "priority": self._make_mock_pipeline(
                ["high", "low", "medium"],
                [0.34, 0.33, 0.33],
            ),
        }

        result = classify_ticket(
            subject="Question",
            body="I have a question about something but not sure what category",
            pipelines=pipelines,
        )

        self.assertTrue(result["escalation"]["required"])


if __name__ == "__main__":
    unittest.main()
