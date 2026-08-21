import json, os, hashlib
from collections import defaultdict
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from .services.academic_api import get_student_details, get_photo_url, get_spi_cpi
import pandas as pd
from .models import ScholarshipMaster, CriteriaMaster, ScholarshipCriteria, StudentScholarshipProfile, StudentScholarship, StudentScholarshipAward
from django.utils import timezone
import time
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from decimal import Decimal, InvalidOperation
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from pypdf import PdfReader, PdfWriter
import zipfile
import tempfile
from django.http import FileResponse
import re
from django.contrib.auth import logout

DOCUMENT_FIELDS = [
    ("Bank Passbook", "bank_passbook_file"),
    ("JEE Certificate", "jee_certificate_file"),
    ("Category Certificate", "category_certificate_file"),
    ("Income Proof", "income_proof_file"),
    ("Class XII Marksheet", "class_12_marksheet_file"),
    ("Odd Semester Fee Receipt", "fee_receipt_odd_semester_file"),
    ("Even Semester Fee Receipt", "fee_receipt_even_semester_file"),
    ("Domicile Certificate", "domicile_certificate_file"),
]
SEMESTER_MAP = {
    "Sem-I": "Semester-I", "Sem-II": "Semester-II", "Sem-III": "Semester-III",
    "Sem-IV": "Semester-IV", "Sem-V": "Semester-V", "Sem-VI": "Semester-VI",
    "Sem-VII": "Semester-VII", "Sem-VIII": "Semester-VIII", "Sem-IX": "Semester-IX",
    "Sem-X": "Semester-X", "Semester-I": "Semester-I", "Semester-II": "Semester-II",
    "Semester-III": "Semester-III", "Semester-IV": "Semester-IV", "Semester-V": "Semester-V",
    "Semester-VI": "Semester-VI", "Semester-VII": "Semester-VII", "Semester-VIII": "Semester-VIII",
    "Semester-IX": "Semester-IX", "Semester-X": "Semester-X",
}
DEPARTMENT_MAP = {
    "Architecture": "Department of Architecture, Planning and Design",
    "Ceramic": "Department of Ceramic Engineering",
    "Chemical": "Department of Chemical Engineering and Technology",
    "Civil": "Department of Civil Engineering",
    "Computer": "Department of Computer Science and Engineering",
    "Computer Science": "Department of Computer Science and Engineering",
    "Electrical": "Department of Electrical Engineering",
    "Electronics": "Department of Electronics Engineering",
    "Mechanical": "Department of Mechanical Engineering",
    "Metallurgical": "Department of Metallurgical Engineering",
    "Mining": "Department of Mining Engineering",
    "Pharmaceutical": "Department of Pharmaceutical Engineering & Technology",
    "Biochemical": "School of Biochemical Engineering",
    "Biomedical": "School of Biomedical Engineering",
    "Decision Science": "NC Jain School of Decision Sciences & Engineering",
    "DSE": "NC Jain School of Decision Sciences & Engineering",
    "Materials": "School of Materials Science and Technology",
    "MST": "School of Materials Science and Technology",
    "Chemistry": "Department of Chemistry",
    "Mathematics": "Department of Mathematical Sciences",
    "Mathematical Sciences": "Department of Mathematical Sciences",
    "Physics": "Department of Physics",
    "Humanities": "Department of Humanistic Studies",
    "Humanistic Studies": "Department of Humanistic Studies",
}

def scholarship_create(request):
    criteria = CriteriaMaster.objects.filter(is_active=True).order_by('display_order')
    if request.method == "POST":
        scholarship = ScholarshipMaster.objects.create(
            scholarship_name=request.POST.get("scholarship_name"),
            description=request.POST.get("description"),
            no_of_scholarships=request.POST.get("no_of_scholarships"),
            scholarship_amount=request.POST.get("scholarship_amount"),
            is_active=True,
        )
        for c in criteria:
            field_name = f"criteria_{c.criteria_id}"
            if c.allowed_operator in ["IN", "NOT_IN"]:
                value = request.POST.getlist(field_name)
                if not value: continue
                value = json.dumps(value)
            else:
                value = request.POST.get(field_name)
                if value is None: continue
                value = value.strip()
                if value == "": continue
            ScholarshipCriteria.objects.create(
                scholarship=scholarship,
                criteria=c,
                operator=c.allowed_operator,
                criteria_value=value,
            )
        messages.success(request, "Scholarship saved successfully.")
        return redirect('scholarship_create')
    return render(request, 'scholarship_create.html', {'criteria': criteria})

def edit_scholarship(request, pk):
    scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=pk)
    criteria = list(CriteriaMaster.objects.filter(is_active=True).order_by('display_order'))
    existing = {sc.criteria.criteria_id: sc for sc in ScholarshipCriteria.objects.filter(scholarship=scholarship)}
    for c in criteria:
        sc = existing.get(c.criteria_id)
        if sc:
            if c.allowed_operator in ["IN", "NOT_IN"]:
                try:
                    c.value = json.loads(sc.criteria_value)
                except json.JSONDecodeError:
                    c.value = []
            else:
                c.value = sc.criteria_value
        else:
            c.value = None
    if request.method == "POST":
        scholarship.scholarship_name = request.POST.get("scholarship_name")
        scholarship.description = request.POST.get("description")
        scholarship.no_of_scholarships = request.POST.get("no_of_scholarships")
        scholarship.scholarship_amount = request.POST.get("scholarship_amount")
        scholarship.save()
        for c in criteria:
            field_name = f"criteria_{c.criteria_id}"
            if c.allowed_operator in ["IN", "NOT_IN"]:
                value = request.POST.getlist(field_name)
                if value:
                    value = json.dumps(value)
                else:
                    value = None
            else:
                value = request.POST.get(field_name)
                if value is not None:
                    value = value.strip()
                if value == "":
                    value = None
            sc = existing.get(c.criteria_id)
            if not value:
                if sc:
                    sc.delete()
                continue
            if sc:
                sc.criteria_value = value
                sc.save()
            else:
                ScholarshipCriteria.objects.create(
                    scholarship=scholarship,
                    criteria=c,
                    operator=c.allowed_operator,
                    criteria_value=value,
                )
        messages.success(request, "Scholarship updated successfully.")
        return redirect('manage_scholarships')
    return render(request, 'scholarship_create.html', {'criteria': criteria, 'scholarship': scholarship})

def common_login(request):
    print("************ common_login() called ************", flush=True)
    if request.user.is_authenticated:
        return redirect("post_login")
    return render(request, "common_login.html")

def google_login(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
    else:
        email = request.GET.get("email", "").strip()

    if not email:
        messages.error(request, "Please enter your email address to continue.")
        return redirect("common_login")
    #email = "aditya.ahirwar.eee23@itbhu.ac.in"
    request.session["email"] = email

    office_users = [
        "ar.sch@itbhu.ac.in",
        "office.sch@itbhu.ac.in",
        "nisha.cis@itbhu.ac.in",
        "adoaa_ug@itbhu.ac.in",
        "adoaa_cc@itbhu.ac.in",
        "doaa@itbhu.ac.in",
    ]

    if email.lower() in office_users:
        request.session["home_url"] = "scholarship_dashboard"
        #messages.success(request, "Signed in as staff.")
        return redirect("scholarship_dashboard")

    request.session["home_url"] = "student_dashboard"
    #messages.success(request, "Signed in as student.")
    return redirect("student_dashboard")


def logout_view(request):
    logout(request)
    request.session.flush()
    #messages.success(request,"You have been logged out.")
    return redirect("common_login")

def student_profile(request):
    student_data = request.session.get("student_data")
    if not student_data:
        return redirect("common_login")

    edit_mode = request.session.pop("edit_profile", False)
    roll_no = student_data["roll_no"]
    existing_award = StudentScholarship.objects.filter(roll_no=roll_no, status='ACTIVE')
    if existing_award.exists():
        return render(request, "already_awarded.html", {"awards": existing_award, "student": student_data})

    if request.method == "POST":
        annual_income = request.POST.get("annual_income")
        class_12_percentage = request.POST.get("class_12_percentage")
        def _coerce_decimal(value):
            if value in (None, ""): return None
            try: return Decimal(str(value))
            except (InvalidOperation, ValueError): return None
        profile, created = StudentScholarshipProfile.objects.get_or_create(roll_no=roll_no, defaults={"institute_email": student_data["email"], "aadhaar_number": "", "bank_name": "", "bank_branch": "", "account_number": "", "ifsc_code": "", "mobile_number": "", "annual_income": Decimal("0")})
        profile.student_name = student_data.get("name", "")
        profile.department = student_data.get("department", "")
        profile.programme = student_data.get("program", "")
        profile.category = student_data.get("category", "")
        profile.current_batch = student_data.get("batch", "")
        profile.current_semester = student_data.get("current_semester", "")
        profile.admission_batch = student_data.get("admission_batch", "")
        profile.institute_email = student_data["email"]
        profile.aadhaar_number = request.POST.get("aadhaar_number")
        profile.bank_name = request.POST.get("bank_name")
        profile.bank_branch = request.POST.get("bank_branch")
        profile.account_number = request.POST.get("account_number")
        profile.ifsc_code = request.POST.get("ifsc_code")
        profile.mobile_number = request.POST.get("mobile_number")
        profile.single_parent_child = request.POST.get("single_parent_child") == "Yes"
        profile.jee_crl_rank = request.POST.get("jee_crl_rank")
        profile.jee_category_rank = request.POST.get("jee_category_rank")
        profile.annual_income = _coerce_decimal(annual_income)
        profile.class_12_percentage = _coerce_decimal(class_12_percentage)
        profile.save()
        return redirect("student_profile_documents")

    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if profile and profile.is_profile_complete and not edit_mode:
        return redirect("eligible_scholarships")
    
    profile_data = request.session.get("student_profile_data")
    if not profile_data and profile:
        profile_data = {
            "aadhaar_number": profile.aadhaar_number,
            "bank_name": profile.bank_name,
            "bank_branch": profile.bank_branch,
            "account_number": profile.account_number,
            "ifsc_code": profile.ifsc_code,
            "mobile_number": profile.mobile_number,
            "single_parent_child": profile.single_parent_child,
            "jee_crl_rank": profile.jee_crl_rank,
            "jee_category_rank": profile.jee_category_rank,
            "annual_income": profile.annual_income,
            "class_12_percentage": profile.class_12_percentage,
        }

    return render(request, "student_profile_details.html", {
        "student": student_data,
        "profile": profile,
        "profile_data": profile_data,
        "edit_mode": edit_mode,
    })


def _profile_document_field_map():
    return {
        "bank_passbook_file": "bank_passbook",
        "jee_certificate_file": "jee_certificate",
        "category_certificate_file": "category_certificate",
        "income_proof_file": "income_proof",
        "class_12_marksheet_file": "class_12_marksheet",
        "fee_receipt_odd_semester_file": "fee_receipt_odd_semester",
        "fee_receipt_even_semester_file": "fee_receipt_even_semester",
        "domicile_certificate_file": "domicile_certificate",
    }


"""def _profile_document_storage_name(roll_no, field_name):
    purpose = _profile_document_field_map().get(field_name, field_name)
    safe_roll = str(roll_no or "student").replace("/", "_").replace("\\", "_")
    return f"{safe_roll}_{purpose}.pdf" """

def _profile_document_storage_name(roll_no, field_name):
    purpose = _profile_document_field_map().get(field_name, field_name)
    safe_roll = str(roll_no or "student").replace("/", "_").replace("\\", "_")
    return f"{safe_roll}_{purpose}_{int(time.time())}.pdf"


def _profile_document_storage_path(roll_no, field_name):
    return _profile_document_storage_name(roll_no, field_name)


def _resolve_document_path(profile, field_name):
    if not profile:
        return None

    value = getattr(profile, field_name, None)
    candidates = []

    if isinstance(value, str) and value:
        candidates.append(value)
    elif value is not None:
        candidate_name = getattr(value, "name", None) or ""
        if candidate_name:
            candidates.append(candidate_name)

    expected_name = _profile_document_storage_name(getattr(profile, "roll_no", None), field_name)
    candidates.append(expected_name)
    candidates.append(os.path.join("documents", expected_name))
    candidates.append(os.path.join(settings.MEDIA_ROOT, expected_name))
    candidates.append(os.path.join(settings.MEDIA_ROOT, "documents", expected_name))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        if os.path.isabs(candidate):
            if os.path.exists(candidate):
                return candidate
            continue

        normalized = candidate.replace("\\", "/")
        if normalized.startswith("media/"):
            normalized = normalized[len("media/"):]

        if os.path.exists(normalized):
            return normalized
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, normalized)):
            return os.path.join(settings.MEDIA_ROOT, normalized)

    return None


def _render_document_to_pdf_bytes(uploaded_file, title):
    if uploaded_file is None:
        return None

    if hasattr(uploaded_file, "read"):
        raw_bytes = uploaded_file.read()
        filename = getattr(uploaded_file, "name", "") or ""
    else:
        raw_bytes = uploaded_file
        filename = ""

    if filename.lower().endswith(".pdf") or str(filename).lower().endswith(".pdf"):
        return raw_bytes

    packet = BytesIO()
    pdf = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, height - 40, title)

    try:
        img = ImageReader(BytesIO(raw_bytes))
        img_w, img_h = img.getSize()
        max_w = width - 80
        max_h = height - 120
        scale = min(max_w / img_w, max_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        x = (width - draw_w) / 2
        y = (height - 80 - draw_h)
        pdf.drawImage(img, x, y, draw_w, draw_h, preserveAspectRatio=True, mask="auto")
    except Exception:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, height - 80, "Unable to render document preview.")

    pdf.save()
    packet.seek(0)
    return packet.getvalue()


"""def _save_profile_document(profile, field_name, uploaded_file):
    if not uploaded_file: return None
    title = _profile_document_field_map().get(field_name, field_name).replace("_", " ").title()
    pdf_bytes = _render_document_to_pdf_bytes(uploaded_file, title)
    if not pdf_bytes:
        return None

    filename = _profile_document_storage_name(getattr(profile, "roll_no", None), field_name)
    output_path = os.path.join(settings.MEDIA_ROOT, filename
    existing_value = getattr(profile, field_name, None)
    if existing_value:
        try:
            if isinstance(existing_value, str):
                candidate_paths = [os.path.join(settings.MEDIA_ROOT, existing_value),
                                    os.path.join(settings.MEDIA_ROOT, "documents", existing_value),]
                for candidate in candidate_paths:
                    if os.path.exists(candidate):
                        os.remove(candidate)
            else:
                existing_value.delete(save=False)
        except Exception:
            pass
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as handle:
        handle.write(pdf_bytes)

    setattr(profile, field_name, filename)
    profile.save(update_fields=[field_name])
    return filename"""

def _save_profile_document(profile, field_name, uploaded_file):
    if not uploaded_file: return None
    title = _profile_document_field_map().get(field_name, field_name).replace("_", " ").title()
    pdf_bytes = _render_document_to_pdf_bytes(uploaded_file, title)
    if not pdf_bytes: return None
    existing_value = getattr(profile, field_name, None)
    filename = _profile_document_storage_name(profile.roll_no, field_name)
    output_path = os.path.join(settings.MEDIA_ROOT, filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as handle: handle.write(pdf_bytes)
    if existing_value:
        try:
            old_name = getattr(existing_value, "name", None)
            if old_name:
                old_path = os.path.join(settings.MEDIA_ROOT, old_name)
                if os.path.exists(old_path): os.remove(old_path)
        except Exception:
            pass
    setattr(profile, field_name, filename)
    profile.save(update_fields=[field_name])
    return filename


def student_profile_documents(request):
    student_data = request.session.get("student_data")
    if not student_data:
        return redirect("common_login")

    roll_no = student_data["roll_no"]
    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if not profile:
        return redirect("student_profile")
    
    if request.method == "POST":
        MAX_FILE_SIZE = 500 * 1024
        for uploaded_file in request.FILES.values():
            if uploaded_file.size > MAX_FILE_SIZE:
                messages.error(request,"Each uploaded file must be smaller than 500 KB. The file '{uploaded_file.name}' is too large.".format(uploaded_file=uploaded_file))
                return redirect("student_profile_documents")
        
        profile = StudentScholarshipProfile.objects.get(roll_no=roll_no)
        for field_name in [
            "bank_passbook_file",
            "jee_certificate_file",
            "category_certificate_file",
            "income_proof_file",
            "class_12_marksheet_file",
            "fee_receipt_odd_semester_file",
            "fee_receipt_even_semester_file",
            "domicile_certificate_file",
        ]:
            uploaded_file = request.FILES.get(field_name)
            if uploaded_file:
                _save_profile_document(profile, field_name, uploaded_file)
        return redirect("student_profile_save")

    return render(request, "student_profile_documents.html", {
        "student": student_data,
        "profile": profile,
        "bank_passbook": file_details(profile.bank_passbook_file) if profile else None,
        "jee_certificate": file_details(profile.jee_certificate_file) if profile else None,
        "category_certificate": file_details(profile.category_certificate_file) if profile else None,
        "income_proof": file_details(profile.income_proof_file) if profile else None,
        "class_12_marksheet": file_details(profile.class_12_marksheet_file) if profile else None,
        "fee_receipt_odd_semester": file_details(profile.fee_receipt_odd_semester_file) if profile else None,
        "fee_receipt_even_semester": file_details(profile.fee_receipt_even_semester_file) if profile else None,
        "domicile_certificate": file_details(profile.domicile_certificate_file) if profile else None,
    })


def student_profile_save(request):
    student_data = request.session.get("student_data")
    if not student_data:
        return redirect("common_login")

    roll_no = student_data["roll_no"]
    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if not profile:
        return redirect("student_profile")

    if request.method == "POST":
        if request.POST.get("no_disciplinary_action") != "on":
            messages.error(request, "You must confirm that no disciplinary action has been taken against you. If any information provided is found to be invalid, disciplinary action may be taken.")
            return redirect("student_profile_save")

        profile.no_disciplinary_action = True
        profile.is_profile_complete = True
        profile.save()
        messages.success(request, "Scholarship profile submitted successfully.")
        return redirect("student_profile_preview")

    ##### GET: Show declaration page   #####
    return render(request, "student_profile_declaration.html", {
        "student": student_data,
        "profile": profile,
        "bank_passbook": file_details(profile.bank_passbook_file),
        "jee_certificate": file_details(profile.jee_certificate_file),
        "category_certificate": file_details(profile.category_certificate_file),
        "income_proof": file_details(profile.income_proof_file),
        "class_12_marksheet": file_details(profile.class_12_marksheet_file),
        "fee_receipt_odd_semester": file_details(profile.fee_receipt_odd_semester_file),
        "fee_receipt_even_semester": file_details(profile.fee_receipt_even_semester_file),
        "domicile_certificate": file_details(profile.domicile_certificate_file),
    })


def student_profile_preview(request):
    student_data = request.session.get("student_data")
    if not student_data:
        return redirect("common_login")
    roll_no = student_data["roll_no"]
    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if not profile:
        return redirect("student_profile")
    if not profile.is_profile_complete:
        return redirect("student_profile")

    return render(request, "student_profile_preview.html", {
        "student": student_data,
        "profile": profile,
        "bank_passbook": file_details(profile.bank_passbook_file),
        "jee_certificate": file_details(profile.jee_certificate_file),
        "category_certificate": file_details(profile.category_certificate_file),
        "income_proof": file_details(profile.income_proof_file),
        "class_12_marksheet": file_details(profile.class_12_marksheet_file),
        "fee_receipt_odd_semester": file_details(profile.fee_receipt_odd_semester_file),
        "fee_receipt_even_semester": file_details(profile.fee_receipt_even_semester_file),
        "domicile_certificate": file_details(profile.domicile_certificate_file),
    })

def edit_student_profile(request):
    student = request.session.get("student_data")
    if not student:
        return redirect("common_login")
    application = StudentScholarship.objects.filter(
        roll_no=student["roll_no"]).exclude(status="REJECTED").first()
    if application:
        messages.error(request, "Profile cannot be edited after applying for a scholarship.")
        return redirect("student_dashboard")
    request.session["edit_profile"] = True
    return redirect("student_profile")

def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"yes", "y", "true", "1", "pass", "passed", "passed with grace", "promoted", "clear"}


def _resolve_student_value(student, *keys, default=None):
    for key in keys:
        value = student.get(key)
        if value not in (None, "", []):
            return value
    return default


def _student_has_failed_grade(student):
    pass_status = str(student.get("pass_status", "")).strip().lower()
    if pass_status in {"yes", "y", "true", "1", "pass", "passed", "passed with grace", "promoted", "clear"}:
        return False
    if pass_status in {"no", "n", "false", "0", "fail", "failed", "not passed", "not pass", "backlog"}:
        return True
    return False


def is_scholarship_eligible(scholarship, student, profile):
    print("\n")
    print("=" * 80)
    print(f"Checking Scholarship : {scholarship.scholarship_name}")
    print(f"Student : {student['name']}")
    print("=" * 80)
    reasons = []
    for criterion in scholarship.criteria.all():
        name = CriteriaMaster.normalize_criteria_name(criterion.criteria.criteria_name)
        print(f"Evaluating Criterion: {name}")
        value = criterion.criteria_value
        if name == "Gender":
            print(f"Gender => Student={student['gender']} Required={value}")
            if student["gender"] != value:
                reason = f"Gender criteria mismatch: expected '{value}', got '{student['gender']}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Program":
            allowed = json.loads(value)
            print(f"Program => Student={student['program']} Allowed={allowed}")
            if student["program"] not in allowed:
                reason = f"Program criteria mismatch: '{student['program']}' is not in {allowed}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Current Semester":
                    allowed = json.loads(value)
                    student_semester = student.get("current_semester") or extract_current_semester(student.get("batch", ""), student.get("admit_year", ""))
                    print(f"Current Semester => Student={student_semester} Allowed={allowed}")
                    if student_semester not in allowed:
                        reason = f"Current semester criteria mismatch: student semester '{student_semester}' is not in {allowed}."
                        reasons.append(reason)
                        print(f"Result => NOT ELIGIBLE: {reason}")
                        return False, reasons
        elif name == "Department":
            allowed = json.loads(value)
            print(f"Department => Student={student['department']} Allowed={allowed}")
            if student["department"] not in allowed:
                reason = f"Department criteria mismatch: '{student['department']}' is not in {allowed}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons        
        elif name == "Income":
            print(f"Income => Student={profile.annual_income} Limit={value}")
            if float(profile.annual_income) > float(value):
                reason = f"Income criteria mismatch: annual income {profile.annual_income} exceeds the limit {value}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Category":
            if student["category"] != value:
                reason = f"Category criteria mismatch: expected '{value}', got '{student['category']}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Age":
            dob = datetime.strptime(student["dob"], "%d-%m-%Y")
            age = datetime.today().year - dob.year
            age_limit = int(float(value))
            print(f"Age => Student={age} Limit={value}")
            if age >= age_limit:
                reason = f"Age criteria mismatch: student age {age} is not below the required limit {age_limit}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Single Parent":
            required = value == "Yes"
            print("profile.single_parent_child: ", profile.single_parent_child)
            if profile.single_parent_child != required:
                reason = f"Single-parent criteria mismatch: required '{required}', got '{profile.single_parent_child}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Disciplinary Action":
            required = value == "Yes"
            student_has_disciplinary_action = not getattr(profile, "no_disciplinary_action", False)
            print(f"Disciplinary Action => Student={student_has_disciplinary_action} Required={required}")
            if student_has_disciplinary_action != required:
                reason = f"Disciplinary-action criteria mismatch: required '{required}', got '{student_has_disciplinary_action}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "SPI":
            required_spi = float(value)
            print(f"SPI => Student={student['spi']} Required={required_spi}")
            if student["spi"] < required_spi:
                reason = f"SPI criteria mismatch: student SPI {student['spi']} is below the required {required_spi}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "CPI":
            required_cpi = float(value)
            print(f"CPI => Student={student['cpi']} Required={required_cpi}")
            if student["cpi"] < required_cpi:
                reason = f"CPI criteria mismatch: student CPI {student['cpi']} is below the required {required_cpi}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Credits Complete":
            required = value == "Yes"
            has_completed_credits = student["credits_earned"] >= 100
            print(f"Credits Complete => Student={has_completed_credits} Required={required}")
            if has_completed_credits != required:
                reason = f"Credits-complete criteria mismatch: required '{required}', got '{has_completed_credits}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name in {"Has Failed Grade", "Pass Status"}:
            required = value == "Yes"
            student_has_failed_grade = _student_has_failed_grade(student)
            print(f"Has Failed Grade => Student={student_has_failed_grade} Required={required}")
            if student_has_failed_grade != required:
                reason = f"Pass-status criteria mismatch: required '{required}', got '{student_has_failed_grade}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
    print(f"Result => ELIGIBLE")
    return True, reasons
            

def eligible_scholarships(request):
    if not request.user.is_authenticated: return redirect("common_login")
    if request.session.get("user_type") != "student": return redirect("common_login")
    student = request.session.get("student_data")
    if not student: return redirect("common_login")
    profile = StudentScholarshipProfile.objects.get(roll_no=student["roll_no"])
    scholarships = ScholarshipMaster.objects.filter(is_active=True)
    eligible = []
    debug_notes = []
    for scholarship in scholarships:
        is_eligible, reasons = is_scholarship_eligible(scholarship, student, profile)
        if is_eligible:
            eligible.append(scholarship)
        else:
            debug_notes.append({"scholarship": scholarship, "reasons": reasons})
    return render(request, "eligible_scholarships.html", {"student": student, "scholarships": eligible, "debug_notes": debug_notes})

def file_details(field):
    if not field:
        return None

    name = ""
    if isinstance(field, str):
        name = field
    else:
        name = getattr(field, "name", "") or ""

    ext = os.path.splitext(name)[1].lower()

    return {
        "filename": os.path.basename(name),
        "is_image": ext in [".jpg", ".jpeg", ".png"],
    }

def normalize_institute_email(email):
    return (email or "").strip().lower().replace("@itbhu.ac.in","@iitbhu.ac.in")

def student_dashboard(request):
    email = request.session.get("email")
    if not email: return redirect("common_login")
    if not request.user.is_authenticated: return redirect("common_login")
    if request.session.get("user_type") != "student": return redirect("common_login")
    student = request.session.get("student_data")
    academic_api_data = request.session.get("academic_api_data")

    # B.Tech and IDD students are allowed to access the scholarship portal. Other programs are not allowed.
    programme = (academic_api_data.get("prg") or "").strip()
    if programme not in ["B.Tech", "IDD"]:
        logout(request)
        request.session.flush()
        messages.error(request, "The Scholarship Portal is presently available only for B.Tech. and IDD students.")
        return redirect("common_login")
    
    google_email = normalize_institute_email(email)
    api_email = normalize_institute_email(academic_api_data.get("email"))

    if not student or google_email != api_email:
        student_payload = get_student_details(email)
        print(type(student_payload))
        print("Student from API =", student_payload)

        if not (student_payload and student_payload.strip()):
            messages.error(request, "Academic server returned an empty response. Please try again later.")
            return redirect("common_login")

        try:
            student_api_data = json.loads(student_payload)
        except Exception as exc:
            print("Student API parse error:", exc)
            messages.error(request, "Unable to read student details from the academic server.")
            return redirect("common_login")

        try:
            spi_data = get_spi_cpi(student_api_data.get("Roll No"), "2025-26-2")

        except Exception as exc:
            print("SPI/CPI API Error:", exc)
            spi_data = {}

        def parse_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        current_batch = (student_api_data.get("Current Batch") or "").strip()
        admission_batch = (student_api_data.get("admit_year") or "").strip()
        current_semester = extract_current_semester(current_batch, admission_batch)

        student = {
            "roll_no": (student_api_data.get("Roll No") or "").strip(),
            "name": student_api_data.get("Name"),
            "gender": student_api_data.get("Gender"),
            "category": student_api_data.get("Category"),
            "program": student_api_data.get("prg"),
            "department": student_api_data.get("dept"),
            "batch": student_api_data.get("Current Batch"),
            "batch": current_batch,
            "current_semester": current_semester,
            "admit_year": admission_batch,
            "email": (student_api_data.get("email") or "").strip(),
            "contact_no": student_api_data.get("contact_no"),
            "admit_year": student_api_data.get("admit_year"),
            "dob": student_api_data.get("dob"),
            "spi": parse_float(spi_data.get("spi")),
            "cpi": parse_float(spi_data.get("cpi")),
            "credits_earned": parse_float(spi_data.get("percent_credits_earned")),
            "pass_status": student_api_data.get("pass_status"),
        }
        # Use the academic API to construct the photograph URL. If anything goes
        # wrong or roll number is missing, keep the value empty so the
        # front-end can choose to show nothing.
        photo_url = ""
        try:
            roll = (student.get("roll_no") or "").strip()
            if roll:
                photo_url = get_photo_url(roll)
        except Exception as exc:
            print("Photo URL generation error:", exc)
            photo_url = ""

        student["photo_url"] = photo_url
        request.session["student_data"] = student

    print("student =", student)
    print("keys =", student.keys())

    student_scholarships = StudentScholarship.objects.filter(roll_no=student["roll_no"]
    ).order_by("-application_date")
    profile = StudentScholarshipProfile.objects.filter(roll_no=student["roll_no"]).first()
    profile_completed = profile.is_profile_complete if profile else False
    edit_mode = request.session.pop("edit_profile", False)
    show_profile_form = (not profile_completed) or edit_mode
    awarded_scholarship = student_scholarships.filter(status="AWARDED").first()
    has_awarded = awarded_scholarship is not None
    print("profile_completed =", profile_completed)
    print("show_profile_form =", show_profile_form)
    context = {
        "bank_passbook": file_details(profile.bank_passbook_file) if profile else None,
        "jee_certificate": file_details(profile.jee_certificate_file) if profile else None,
        "category_certificate": file_details(profile.category_certificate_file) if profile else None,
        "income_proof": file_details(profile.income_proof_file) if profile else None,
        "class_12_marksheet": file_details(profile.class_12_marksheet_file) if profile else None,
        "fee_receipt_odd_semester": file_details(profile.fee_receipt_odd_semester_file) if profile else None,
        "fee_receipt_even_semester": file_details(profile.fee_receipt_even_semester_file) if profile else None,
        "domicile_certificate": file_details(profile.domicile_certificate_file) if profile else None,
    }
    return render(request, "student_dashboard.html", 
                  {"student": student, "student_scholarships": student_scholarships, 
                   "profile": profile, "profile_completed": profile_completed, 
                   "show_profile_form": show_profile_form, "has_awarded": has_awarded,
                   "awarded_scholarship": awarded_scholarship, **context})

def scholarship_detail(request, scholarship_id):
    scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=scholarship_id)
    student = request.session.get("student_data")
    already_applied = False
    if student:
        already_applied = StudentScholarship.objects.filter(roll_no=student["roll_no"],scholarship=scholarship).exists()
    return render(request, "scholarship_detail.html", {"scholarship": scholarship, "already_applied": already_applied})


def download_bulk_upload_template(request):
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scholarship_bulk_upl_template.xlsx",
    )
    if not os.path.exists(template_path):
        raise Http404("Template file not found.")
    response = FileResponse(open(template_path, "rb"), as_attachment=True)
    response["Content-Disposition"] = "attachment; filename=scholarship_bulk_upl_template.xlsx"
    return response


def bulk_upload_scholarships(request):
    if request.method == "GET": return render(request, "bulk_upload_scholarships.html")
    file = request.FILES["file"]
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    criteria_lookup = {CriteriaMaster.normalize_criteria_name(c.criteria_name): c for c in CriteriaMaster.objects.all()}
    uploaded = 0
    mapping = {
        "Gender (=) ": "Gender",
        "Program (In)": "Program",
        "Current Semester (In)": "Current Semester",
        "Department (In)": "Department",
        "CPI (>)": "CPI",
        "SPI (>)": "SPI",
        "Income (<)": "Income",
        "Category (=)": "Category",
        "Grade (Not in)": "Has Failed Grade",
        "Age (<)": "Age",
        "Credits Complete (Yes/No)": "Credits Complete",
        "Single Parent (Yes/No)": "Single Parent",
        "Disciplinary Action (Yes/No)": "Disciplinary Action",
    }
   
    for _, row in df.iterrows():
        scholarship = ScholarshipMaster.objects.create(
            scholarship_name=str(row["Name of Scholarship "]).strip(),
            description=str(row["Terms & Conditions"]),
            no_of_scholarships=str(row["No. of Scholarship(s) for award"]),
            scholarship_amount=str(row["Amount (Rs.)"]),
        )
        for excel_column, criteria_name in mapping.items():
            value = row.get(excel_column)
            if pd.isna(value): continue
            criteria = criteria_lookup.get(CriteriaMaster.normalize_criteria_name(criteria_name))
            if not criteria: continue
            criteria_value = str(value).strip()
            if criteria.allowed_operator in ["IN", "NOT_IN"]:
                values = [x.strip() for x in criteria_value.split(",")]
                if criteria_name == "Current Semester":
                    values = [SEMESTER_MAP.get(v, v) for v in values]
                elif criteria_name == "Department":
                    values = [DEPARTMENT_MAP.get(v, v) for v in values]
                criteria_value = json.dumps(values)
            elif criteria_name == "Department":
                criteria_value = DEPARTMENT_MAP.get(criteria_value, criteria_value)
            elif criteria_name == "Current Semester":
                criteria_value = SEMESTER_MAP.get(criteria_value, criteria_value)
            ScholarshipCriteria.objects.create(
                scholarship=scholarship,
                criteria=criteria,
                operator=criteria.allowed_operator,
                criteria_value=criteria_value,
            )
        uploaded += 1
    messages.success(request, f"{uploaded} scholarships uploaded successfully.")
    return redirect("scholarship_create")

def manage_scholarships(request):
    query = request.GET.get("q", "").strip()
    scholarships = ScholarshipMaster.objects.filter(is_active=True)
    if query:
        scholarships = scholarships.filter(
            Q(scholarship_name__icontains=query)
            | Q(description__icontains=query)
            | Q(scholarship_amount__icontains=query)
            | Q(no_of_scholarships__icontains=query)
        )
    scholarships = scholarships.order_by("scholarship_name")

    return render(request, "manage_scholarships.html", {"scholarships": scholarships})

def view_scholarship(request, pk):

    scholarship = get_object_or_404(ScholarshipMaster,scholarship_id=pk)

    criteria = ScholarshipCriteria.objects.filter(scholarship=scholarship
                                                  ).select_related("criteria")


    return render(request, "view_scholarship.html",{"scholarship": scholarship,
            "criteria": criteria})


def delete_scholarship(request, pk):
    if request.method == "POST":
        scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=pk)
        scholarship.delete()
        messages.success(request, "Scholarship deleted successfully.")
    return redirect('manage_scholarships')

def scholarship_dashboard(request):

    context = {
        "total_scholarships": ScholarshipMaster.objects.count(),
        "active_scholarships": ScholarshipMaster.objects.filter(is_active=True).count(),
        "applications": StudentScholarship.objects.exclude(status="REJECTED").count(),
        "awarded": StudentScholarship.objects.filter(status="AWARDED").count(),
    }

    return render(request, "scholarship_dashboard.html", context)



def apply_scholarship(request, scholarship_id):

    if request.method != "POST":
        return redirect("scholarship_detail", scholarship_id=scholarship_id)

    student = request.session.get("student_data")
    if not student:
        return redirect("common_login")

    roll_no = student["roll_no"]

    # Student is already awarded scholarship
    if StudentScholarship.objects.filter(roll_no=roll_no, status="AWARDED").exists():    
        messages.warning(request, "You have already applied for a scholarship. Multiple applications are not permitted.")
        return redirect("student_dashboard")
    # Student has already applied for the same scholarship
    if StudentScholarship.objects.filter(roll_no=roll_no, scholarship_id=scholarship_id, status="APPLIED").exists():
        messages.warning(request, "You have already applied for this scholarship. Multiple applications are not permitted.")
        return redirect("student_dashboard")
    scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=scholarship_id,
        is_active=True)

    StudentScholarship.objects.create(roll_no=roll_no, scholarship=scholarship,
        status="APPLIED")

    messages.success(request, "Your scholarship application has been submitted successfully.")

    return redirect("student_dashboard")




def assign_scholarship(request):
  student = None
  student_applications = None  
  
  if request.method == "POST":
    action = request.POST.get("action")
    roll_no = request.POST.get("roll_no")  
    # FETCH STUDENT
    if action == "fetch":      
      try:
        student_json = get_student_details(roll_no)
        student = json.loads(student_json)
        student = {
          "roll_no": student.get("Roll No"),
          "name": student.get("Name"),
          "gender": student.get("Gender"),
          "category": student.get("Category"),
          "dob": student.get("dob"),
          "contact_no": student.get("contact_no"),
          "email": student.get("email"),
          "program": student.get("prg"),
          "admit_year": student.get("admit_year"),
          "pass_status": student.get("pass_status"),
          "department": student.get("dept"),
          "current_batch": student.get("Current Batch"),
          "address": student.get("Address"),
        }
        print("FETCH ROLL =", roll_no)
        print(
            "APPLICATIONS =",
            StudentScholarship.objects.filter(
                roll_no=roll_no
            ).count()
        )
        student_applications = StudentScholarship.objects.filter(roll_no=roll_no).select_related("scholarship")
        print("Student Data =", student)
      except Exception:
        messages.error(request, "Student not found.")
    # AWARD SCHOLARSHIP
    elif action == "award":
        print("AWARD ROLL =", roll_no)
        print("SCHOLARSHIP ID =", request.POST.get("scholarship_id"))
        scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=request.POST.get("scholarship_id"))
        application = StudentScholarship.objects.filter(roll_no=roll_no, scholarship=scholarship).first()
        if application is None:
            messages.error(request, "No scholarship application was found for this student and scholarship.")
            return redirect("assign_scholarship")
        if StudentScholarship.objects.filter(roll_no=roll_no, status="AWARDED").exclude(id=application.id).exists():
            messages.error(request, "This student has already been awarded another scholarship.")
            return redirect("assign_scholarship")
        if application.status == "AWARDED":
            messages.error(request, "This scholarship is already awarded to the student.")
            return redirect("assign_scholarship")
        success, msg = award_application(application)
        if success:
            messages.success(request,f"{scholarship.scholarship_name} awarded successfully.")
        else:
            messages.error(request, msg)
        return redirect("scholarship_dashboard")
  return render(request, "assign_scholarship.html", {
    "student": student,
    "student_applications": student_applications,
    "current_year": timezone.now().year,
  })

def award_application(application):
    """Award an already fetched StudentScholarship application.Returns (success, message)"""
    if application.status == "AWARDED":
        return False, "Scholarship already awarded."
    if StudentScholarship.objects.filter(
            roll_no=application.roll_no,
            status="AWARDED"
    ).exclude(id=application.id).exists():
        return False, "Student has already been awarded another scholarship."
    application.status = "AWARDED"
    application.award_year = timezone.now().year
    application.save()
    award, created = StudentScholarshipAward.objects.get_or_create(
        student_scholarship=application,
        defaults={
            'decision_date': timezone.now(),
        }
    )
    if not created and award.decision_date is None:
        award.decision_date = timezone.now()
        award.save()
    return True, "Awarded successfully."


def _format_bulk_award_failure_reason(reason):
    friendly_map = {
        "Scholarship not found": "the scholarship name could not be matched",
        "Student has not applied": "the student has not applied for that scholarship",
        "Scholarship already awarded": "the scholarship was already awarded",
        "Student has already been awarded another scholarship.": "the student has already been awarded another scholarship",
    }
    return friendly_map.get(reason, reason)


def _build_bulk_award_failure_summary(errors):
    reason_counts = {}
    for error in errors:
        reason = error.get("Reason", "Unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    if not reason_counts:
        return ""

    detail_parts = []
    for reason, count in sorted(reason_counts.items()):
        detail_parts.append(f"{count} row(s) were skipped because {_format_bulk_award_failure_reason(reason)}")
    return "Summary: " + "; ".join(detail_parts)


def remove_scholarship_application(request, application_id):
    student = request.session.get("student_data")
    application = get_object_or_404(StudentScholarship, id=application_id, roll_no=student["roll_no"])
    if application.status == "AWARDED":
        messages.error(request, "Awarded scholarships cannot be removed.")
    else:
        application.delete()
        messages.success(request, "Scholarship application removed successfully.")
    return redirect("student_dashboard")

def bulk_award_scholarships(request):
    if request.method == "GET": return render(request, "bulk_award_scholarships.html")
    file = request.FILES["file"]
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    required_columns = ["Student Roll Number", "Scholarship Name"]
    missing = [c for c in required_columns if c not in df.columns]
    if missing: messages.error(request, "Missing columns : " + ", ".join(missing)); return redirect("bulk_award_scholarships")
    success = failed = 0
    errors = []
    for index, row in df.iterrows():
        roll_no = str(row["Student Roll Number"]).strip()
        scholarship_name = str(row["Scholarship Name"]).strip()
        scholarships_qs = ScholarshipMaster.objects.filter(scholarship_name__iexact=scholarship_name.strip(), is_active=True)
        count = scholarships_qs.count()
        if count == 0:
            failed += 1
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": "Scholarship not found"})
            continue
        scholarship = scholarships_qs.first()
        if count > 1:
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": f"Multiple scholarships matched ({count}); using first match."})
        application = StudentScholarship.objects.filter(roll_no=roll_no, scholarship=scholarship).first()
        if application is None:
            failed += 1
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": "No matching scholarship application found"})
            continue
        if application.status == "AWARDED":
            failed += 1
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": "Scholarship already awarded"})
            continue
        if StudentScholarship.objects.filter(roll_no=roll_no, status="AWARDED").exclude(id=application.id).exists():
            failed += 1
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": "Student has already been awarded another scholarship."})
            continue
        if application.status != "APPLIED":
            failed += 1
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": f"Application is not in APPLIED status (current: {application.status})"})
            continue
        ok, msg = award_application(application)
        if ok:
            success += 1
        else:
            failed += 1
            errors.append({"Line Number": index + 2, "Student Roll Number": roll_no, "Scholarship Name": scholarship_name, "Reason": msg})
    report_name = "bulk_award_errors.xlsx"
    report_path = os.path.join(settings.MEDIA_ROOT, report_name)
    report_ready = False
    if errors:
        media_root = str(settings.MEDIA_ROOT)
        try:
            os.makedirs(media_root, exist_ok=True)
            error_df = pd.DataFrame(errors)
            error_df.to_excel(report_path, index=False)
            report_ready = os.path.exists(report_path)
        except Exception as e:
            messages.error(request, f"Failed to save error report: {e}")
    if success:
        messages.success(request, f"{success} scholarship(s) awarded successfully.")
    elif not errors:
        messages.info(request, "No scholarships were awarded from this file.")
    if failed:
        summary = _build_bulk_award_failure_summary(errors)
        if report_ready:
            download_url = reverse("download_bulk_award_report")
            messages.warning(request, format_html(
                "{} record(s) skipped. <a href='{}' target='_blank' download>Download the skipped rows report</a> for line numbers and reasons. {}",
                failed,
                download_url,
                summary,
            ))
        else:
            messages.warning(request, f"{failed} record(s) skipped. {summary}")
    return redirect("bulk_award_scholarships")


def download_bulk_award_report(request):
    report_path = os.path.join(settings.MEDIA_ROOT, "bulk_award_errors.xlsx")
    if not os.path.exists(report_path):
        raise Http404("Report not found.")
    return FileResponse(open(report_path, "rb"), as_attachment=True, filename="bulk_award_errors.xlsx")


def download_award_template(request):
    template_path = os.path.join(settings.BASE_DIR, "templates","Award_Scholarship_Template.xlsx",)
    if not os.path.exists(template_path):
        raise Http404("Template not found.")
    return FileResponse(open(template_path, "rb"), as_attachment=True, filename="Award_Scholarship_Template.xlsx",)

def application_management(request):

    scholarships = ScholarshipMaster.objects.filter(
        is_active=True
    ).order_by("scholarship_name")
    departments = sorted(set(DEPARTMENT_MAP.values()))
    applications = StudentScholarship.objects.none()
    searched = False

    roll_no = request.GET.get("roll_no", "").strip()
    department = request.GET.get("department", "").strip()
    scholarship_id = request.GET.get("scholarship", "").strip()
    all_students = request.GET.get("all")

    if roll_no:
        searched = True
        applications = StudentScholarship.objects.filter(roll_no=roll_no)

    elif department:
        searched = True
        roll_nos = StudentScholarshipProfile.objects.filter(department=department).values_list("roll_no", flat=True)
        applications = StudentScholarship.objects.filter(roll_no__in=roll_nos)

    elif scholarship_id:
        searched = True
        applications = StudentScholarship.objects.filter(scholarship_id=scholarship_id)

    elif all_students:
        searched = True
        applications = StudentScholarship.objects.all()

    applications = applications.select_related("scholarship").order_by("roll_no","scholarship__scholarship_name")

    applications = applications.select_related("scholarship")

    student_rows = []
    grouped = {}
    for app in applications:
        if app.roll_no not in grouped:
            profile = StudentScholarshipProfile.objects.filter(roll_no=app.roll_no).first()
            grouped[app.roll_no] = {
                "roll_no": app.roll_no,
                "student_name": profile.student_name if profile else "",
                "department": profile.department if profile else "",
                "programme": profile.programme if profile else "",
                "applications": 0,
            }
        grouped[app.roll_no]["applications"] += 1
    student_rows = list(grouped.values())

    return render(
        request,
        "application_management.html",
        {
            "scholarships": scholarships,
            "departments": departments,
            "student_rows": student_rows,
            "searched": searched,
            "roll_no": roll_no,
            "department": department,
            "scholarship_id": scholarship_id,
            "all_students": all_students,
        },
    )

def application_detail(request, roll_no):
    profile = get_object_or_404(StudentScholarshipProfile, roll_no=roll_no)
    applications = (
        StudentScholarship.objects.filter(roll_no=roll_no)
        .select_related("scholarship")
        .order_by("scholarship__scholarship_name")
    )
    return render(request, "application_detail.html", {"profile": profile, "applications": applications})

def download_application_pdf(request, roll_no):
    profile = get_object_or_404(StudentScholarshipProfile, roll_no=roll_no)
    applications = (
        StudentScholarship.objects.filter(roll_no=roll_no)
        .select_related("scholarship")
        .order_by("scholarship__scholarship_name")
    )
    return FileResponse(build_application_pdf(profile, applications), as_attachment=True, filename=f"{roll_no}_application.pdf")


def build_application_pdf(profile, applications):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    heading, subheading = styles["Heading1"], styles["Heading2"]
    heading.alignment = TA_CENTER
    story = [
        Paragraph("Scholarship Application Details", heading),
        Paragraph("<b>Indian Institute of Technology (BHU), Varanasi</b>", heading),
        Paragraph("<b>Scholarship Application</b>", heading),
        Spacer(1, 0.5*cm),
    ]

    student_table = [
        ["Roll Number", profile.roll_no], ["Name", profile.student_name],
        ["Department", profile.department], ["Programme", profile.programme],
        ["Category", profile.category], ["Current Batch", profile.current_batch],
    ]
    table = Table(student_table, colWidths=[5*cm, 11*cm])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.extend([table, Spacer(1, 0.5*cm), Paragraph("<b>Scholarships Applied</b>", subheading)])

    scholarship_rows = [["Scholarship", "Status", "Applied On"]]
    scholarship_rows.extend([
        [app.scholarship.scholarship_name, app.status, app.application_date.strftime("%d-%m-%Y")]
        for app in applications
    ])
    table = Table(scholarship_rows, colWidths=[9*cm, 3*cm, 4*cm])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))
    story.extend([table, PageBreak(), Paragraph("<b>Student Scholarship Profile</b>", subheading)])

    profile_rows = [
        ["Institute Email", profile.institute_email], ["Aadhaar Number", profile.aadhaar_number],
        ["Annual Income", profile.annual_income], ["Bank Name", profile.bank_name],
        ["Branch", profile.bank_branch], ["Account Number", profile.account_number],
        ["IFSC", profile.ifsc_code], ["Mobile", profile.mobile_number],
        ["Single Parent Child", "Yes" if profile.single_parent_child else "No"],
        ["JEE CRL Rank", profile.jee_crl_rank], ["JEE Category Rank", profile.jee_category_rank],
        ["Class XII Percentage", profile.class_12_percentage],
    ]
    table = Table(profile_rows, colWidths=[6*cm, 10*cm])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (0,-1), colors.lightgrey),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(table)

    doc.build(story)
    buffer.seek(0)

    writer, reader = PdfWriter(), PdfReader(buffer)
    for page in reader.pages:
        writer.add_page(page)
    for _, field in DOCUMENT_FIELDS:
        file = getattr(profile, field)
        if file:
            try:
                for page in PdfReader(file.path).pages:
                    writer.add_page(page)
            except Exception:
                pass

    final_pdf = BytesIO()
    writer.write(final_pdf)
    return final_pdf.seek(0) or final_pdf

def download_applications(request):
    print("##############Roll numbers received:", request.POST.getlist("roll_nos"))
    if request.method != "POST":
        return redirect("application_management")

    roll_nos = request.POST.getlist("roll_nos")
    if not roll_nos:
        return redirect("application_management")
    if len(roll_nos) == 1:
        return download_application_pdf(request, roll_nos[0])

    temp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(temp.name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for roll_no in roll_nos:
            profile = StudentScholarshipProfile.objects.get(roll_no=roll_no)
            applications = (
                StudentScholarship.objects.filter(roll_no=roll_no)
                .select_related("scholarship")
                .order_by("scholarship__scholarship_name")
            )
            pdf = build_application_pdf(profile, applications)
            zipf.writestr(f"{roll_no}_application.pdf", pdf.getvalue())

    temp.seek(0)
    return FileResponse(open(temp.name, "rb"), as_attachment=True, filename="Scholarship_Applications.zip")


def extract_current_semester(current_batch, admit_year=""):
    if not current_batch:
        return ""
    text = str(current_batch).strip()
    # Normal API value: IX-Semester / Semester-IX
    match = re.search(r'\bSemester[-\s]*([IVX]+)\b|([IVX]+)[-\s]*Semester\b', text, re.IGNORECASE)
    if match:
        return f"Semester-{(match.group(1) or match.group(2)).upper()}"
    # Fallback: derive from current academic year
    if admit_year:
        admission_year = int(admit_year.split("-")[0])
        today = datetime.today()
        # Academic year: July to June
        current_academic_year = today.year if today.month >= 7 else today.year - 1
        semester = (current_academic_year - admission_year) * 2 + 1
        roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
        if 1 <= semester <= len(roman):
            return f"Semester-{roman[semester - 1]}"
    return ""

def post_login(request):
    """Entry point after successful Google authentication."""
    print("\n========== POST LOGIN DEBUG ==========", flush=True)
    print("Authenticated:", request.user.is_authenticated, flush=True)
    print("User:", request.user, flush=True)
    print("User email:", request.user.email, flush=True)
    print("Session:", dict(request.session), flush=True)
    print("user_type:", request.session.get("user_type"), flush=True)
    print("email:", request.session.get("email"), flush=True)
    print("=======================================\n", flush=True)

    if not request.user.is_authenticated:
        return redirect("common_login")
    email = (request.user.email or request.session.get("email", "")).strip().lower()
    #email =  "aditi.saha.mec22@itbhu.ac.in"  # Hardcoded for testing purposes; replace with the line above in production
    if not email:
        messages.error(request, "Unable to determine your authenticated email address.")
        return redirect("common_login")
        

    request.session["email"] = email
    user_type = request.session.get("user_type")

    if user_type == "staff":
        return redirect("scholarship_dashboard")
    if user_type == "student":
        return redirect("student_dashboard")
    # Safety fallback: do not allow unauthenticated Google users into student portal
    request.session.flush()
    messages.error(request, "Your account could not be verified for this portal.")
    return redirect("common_login")
