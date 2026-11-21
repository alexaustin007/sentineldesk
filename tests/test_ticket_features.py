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

        # Word vocab is inside the FeatureUnion
        word_vocab = features.named_steps["tfidf"].transformer_list[0][1].vocabulary_
        self.assertIn("vpn down", word_vocab)
        self.assertIn("verbindung gestört", word_vocab)
        self.assertNotIn("hiddenlabel", word_vocab)
        self.assertNotIn("hiddenanswer", word_vocab)

        live = features.transform([{"body": "Verbindung gestört"}, {"body": "newterm"}])
        self.assertEqual(live.shape[1], matrix.shape[1])
        self.assertEqual(live[1].nnz, 0)
        self.assertNotIn("newterm", word_vocab)
