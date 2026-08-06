import os
from io import BytesIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from datetime import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from pypdf import PdfReader

from sch_master.views import is_scholarship_eligible, _build_student_pdf, _save_profile_document


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


class ApplicationPdfTests(TestCase):
    def test_save_profile_document_writes_roll_numbered_file_in_media_root(self):
        class DummyProfile:
            def __init__(self, roll_no):
                self.roll_no = roll_no
                self.saved_fields = []

            def save(self, update_fields=None):
                self.saved_fields.append(update_fields)

        profile = DummyProfile("12345")
        uploaded = SimpleUploadedFile("sample.png", b"dummy-image", content_type="image/png")

        with TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=media_dir):
                saved_name = _save_profile_document(profile, "bank_passbook_file", uploaded)

        self.assertEqual(saved_name, "12345_bank_passbook.pdf")
        self.assertTrue(os.path.exists(os.path.join(media_dir, saved_name)))

    def test_build_student_pdf_creates_multiple_pages_for_sections(self):
        class FakeFileField:
            def __init__(self, name, content):
                self.name = name
                self._content = content

            def open(self, mode="rb"):
                self._opened = True
                return self

            def read(self):
                return self._content

            def close(self):
                self._opened = False

        student = {
            "name": "Test Student",
            "department": "CSE",
            "program": "B.Tech",
            "batch": "2025",
            "spi": 8.5,
            "cpi": 8.0,
            "category": "GEN",
            "gender": "Male",
            "email": "student@example.com",
            "dob": "01-01-2000",
            "admit_year": "2021",
        }
        profile = SimpleNamespace(
            institute_email="student@example.com",
            aadhaar_number="123412341234",
            mobile_number="9876543210",
            bank_name="Test Bank",
            bank_branch="Main Branch",
            account_number="12345",
            ifsc_code="TEST0001",
            single_parent_child=False,
            jee_crl_rank=1000,
            jee_category_rank=100,
            annual_income=500000,
            class_12_percentage=90.0,
            no_disciplinary_action=True,
            is_profile_complete=True,
            bank_passbook_file=FakeFileField("passbook.txt", b"dummy"),
            jee_certificate_file=None,
            category_certificate_file=None,
            income_proof_file=None,
            class_12_marksheet_file=None,
            fee_receipt_odd_semester_file=None,
            fee_receipt_even_semester_file=None,
            domicile_certificate_file=None,
        )
        applications = [
            SimpleNamespace(
                scholarship=SimpleNamespace(scholarship_name="Merit Scholarship"),
                status="APPLIED",
                application_date=datetime(2025, 1, 10),
            )
        ]

        pdf_bytes = _build_student_pdf("12345", student, profile, applications, include_documents=True)
        reader = PdfReader(BytesIO(pdf_bytes))

        self.assertGreaterEqual(len(reader.pages), 3)
