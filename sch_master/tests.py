from types import SimpleNamespace

from django.test import TestCase

from sch_master.views import is_scholarship_eligible


class FakeCriteriaManager:
    def __init__(self, criteria):
        self._criteria = criteria

    def all(self):
        return self._criteria


class EligibilityDebugTests(TestCase):
    def test_returns_reason_when_criterion_does_not_match(self):
        student = {
            "name": "Test Student",
            "gender": "Male",
            "program": "B.Tech",
            "department": "CSE",
            "category": "GEN",
            "dob": "01-01-2000",
            "spi": 8.5,
            "cpi": 8.0,
            "credits_earned": 120,
            "pass_status": "pass",
        }
        profile = SimpleNamespace(annual_income=500000, single_parent_child=False, no_disciplinary_action=True)
        scholarship = SimpleNamespace(
            scholarship_name="Needle Scholarship",
            criteria=FakeCriteriaManager([
                SimpleNamespace(
                    criteria=SimpleNamespace(criteria_name="Gender"),
                    criteria_value="Female",
                )
            ]),
        )

        eligible, reasons = is_scholarship_eligible(scholarship, student, profile)

        self.assertFalse(eligible)
        self.assertTrue(reasons)
        self.assertIn("Gender", reasons[0])
