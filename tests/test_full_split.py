import tempfile
import unittest
from pathlib import Path

from scripts.prepare_data import GERMAN_SOURCE, SOURCE, V5_SOURCE, split_full


class FullSplitTest(unittest.TestCase):
    def test_overlapping_versions_keep_one_id_and_bodies_stay_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            header = "subject,body,answer,type,queue,priority,language\n"
            labels = "Incident,IT Support,high,en\n"
            (data / SOURCE.name).write_text(
                header
                + "VPN,No connection,,"
                + labels
                + ",Login failed,Reset,"
                + labels
            )
            (data / V5_SOURCE.name).write_text(
                header
                + "vpn,NO CONNECTION,Restart,"
                + labels
                + "Network,No connection,Restart,"
                + labels
                + "Skip, ,Unused,"
                + labels
            )
            (data / GERMAN_SOURCE.name).write_text(
                "subject,body,queue,priority,language\nA,B,Support,low,de\n"
            )
            train, holdout = split_full(data)
        tickets = {row["ticket_id"]: row for row in train + holdout}
        self.assertEqual(set(tickets), {"TKT-00001", "TKT-00002", "TKT-V5-00002"})
        self.assertEqual(tickets["TKT-00001"]["answer"], "Restart")
        self.assertTrue(
            {r["body"] for r in train}.isdisjoint(r["body"] for r in holdout)
        )
