import unittest

from ricebridge.engine import Demo
from ricebridge.scenario_data import (
    FAMILY,
    FIELD_IDS,
    FIELDS,
    HTX,
    HTX_OFFICER,
    NEIGHBOUR,
    REMEASURERS,
    SENDERS,
    TECHNICAL,
)

HERO_F2 = [
    {"name": "Hộ thửa 2, same gauge", "role": "re-photograph the same tube", "walk_min": 0, "response_rate": 0.88, "independent": False},
    {"name": "Hộ thửa 2, gauge near the inlet", "role": "farmer measures a second tube", "walk_min": 2, "response_rate": 0.88, "independent": True},
    {"name": HTX_OFFICER, "role": "HTX officer measures a second tube", "walk_min": 12, "response_rate": 0.95, "independent": True},
]


def independent(options):
    return [o["name"] for o in options if o["independent"]]


class Remeasurers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = Demo(llm_mode="rules")

    def test_every_field_has_family_neighbour_htx_and_technical_officer(self):
        self.assertEqual(sorted(REMEASURERS), sorted(FIELD_IDS))
        for fid, registry in REMEASURERS.items():
            with self.subTest(fid=fid):
                self.assertLessEqual({FAMILY, NEIGHBOUR, HTX, TECHNICAL}, {r.relation for r in registry})
                self.assertGreaterEqual(sum(r.independent for r in registry), 2)

    def test_candidates_for_returns_two_independent_people_for_every_field(self):
        for fid in FIELD_IDS:
            with self.subTest(fid=fid):
                self.assertGreaterEqual(len(independent(self.demo.candidates_for(fid))), 2)

    def test_disputed_sender_is_never_counted_as_independent(self):
        owners = {f.fid: f.owner for f in FIELDS}
        for fid in FIELD_IDS:
            for sender in [*SENDERS, owners[fid]]:
                with self.subTest(fid=fid, sender=sender):
                    picks = independent(self.demo.candidates_for(fid, sender))
                    self.assertGreaterEqual(len(picks), 2)
                    self.assertNotIn(sender, picks)

    def test_ba_sau_field_needs_someone_other_than_her_and_the_htx_recorder(self):
        f3 = next(f for f in FIELDS if f.fid == "F3")
        self.assertIn("74", f3.note)
        self.assertIn("no smartphone", f3.note)
        picks = independent(self.demo.candidates_for("F3", HTX_OFFICER))
        self.assertEqual(picks, ["Hộ thửa bên cạnh", "Cán bộ kỹ thuật"])

    def test_f2_hero_candidates_are_unchanged(self):
        self.assertEqual(self.demo.candidates_for("F2", "Hộ thửa 2"), HERO_F2)
        self.assertEqual(self.demo.candidates_for("F2"), HERO_F2)


if __name__ == "__main__":
    unittest.main()
