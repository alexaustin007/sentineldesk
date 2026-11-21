import unittest

from ticket_features import make_ticket_features


class TicketFeaturesTest(unittest.TestCase):
    def test_training_and_inference_share_text_only_features(self) -> None:
        features = make_ticket_features()
        rows = [
            {"subject": "VPN down", "body": "Cannot connect", "queue": "hiddenlabel"},
            {"subject": None, "body": "Verbindung gestört", "answer": "hiddenanswer"},
            {"subject": "VPN down", "body": "Verbindung gestört"},
        ]
        matrix = features.fit_transform(rows)
        vocab = features.named_steps["tfidf"].vocabulary_
        self.assertIn("vpn down", vocab)
        self.assertIn("verbindung gestört", vocab)
        self.assertNotIn("hiddenlabel", vocab)
        self.assertNotIn("hiddenanswer", vocab)

        live = features.transform([{"body": "Verbindung gestört"}, {"body": "newterm"}])
        self.assertEqual(live.shape[1], matrix.shape[1])
        self.assertEqual(live[1].nnz, 0)
        self.assertNotIn("newterm", vocab)
