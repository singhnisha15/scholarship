import os
import django
from io import BytesIO
from datetime import datetime
from types import SimpleNamespace
from pypdf import PdfReader

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scholarship.settings')
django.setup()

from sch_master.views import _build_student_pdf, _save_profile_document
from sch_master.models import StudentScholarshipProfile

class FakeFileField:
    def __init__(self, name, content):
        self.name = name
        self._content = content
    def open(self, mode='rb'):
        return self
    def read(self):
        return self._content
    def close(self):
        pass

profile = StudentScholarshipProfile(roll_no='ROLL123')
profile.bank_passbook_file = None
profile.jee_certificate_file = None
profile.category_certificate_file = None
profile.income_proof_file = None
profile.class_12_marksheet_file = None
profile.fee_receipt_odd_semester_file = None
profile.fee_receipt_even_semester_file = None
profile.domicile_certificate_file = None

_save_profile_document(profile, 'bank_passbook_file', FakeFileField('bank_passbook.jpg', b'fake-image'))
print('saved=', profile.bank_passbook_file)
student = {'name':'Test','department':'CSE','program':'B.Tech','batch':'2025','spi':8.5,'cpi':8.0,'category':'GEN','gender':'Male','email':'test@example.com','dob':'01-01-2000','admit_year':'2021'}
applications=[SimpleNamespace(scholarship=SimpleNamespace(scholarship_name='Merit Scholarship'), status='APPLIED', application_date=datetime(2025,1,10))]
pdf_bytes = _build_student_pdf('ROLL123', student, profile, applications, include_documents=True)
reader = PdfReader(BytesIO(pdf_bytes))
print('pages=', len(reader.pages))
print(reader.pages[0].extract_text()[:120])
print(reader.pages[2].extract_text()[:120])
