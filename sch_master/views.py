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
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

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
    print("************ common_login() called ************")
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
    ]

    if email.lower() in office_users:
        request.session["home_url"] = "scholarship_dashboard"
        messages.success(request, "Signed in as staff.")
        return redirect("scholarship_dashboard")

    request.session["home_url"] = "student_dashboard"
    messages.success(request, "Signed in as student.")
    return redirect("student_dashboard")


def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
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

    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if profile and profile.is_profile_complete and not edit_mode:
        return redirect("eligible_scholarships")

    if request.method == "POST":
        request.session["student_profile_data"] = {
            "institute_email": student_data["email"],
            "aadhaar_number": request.POST.get("aadhaar_number"),
            "bank_name": request.POST.get("bank_name"),
            "bank_branch": request.POST.get("bank_branch"),
            "account_number": request.POST.get("account_number"),
            "ifsc_code": request.POST.get("ifsc_code"),
            "mobile_number": request.POST.get("mobile_number"),
            "single_parent_child": request.POST.get("single_parent_child") == "Yes",
            "jee_crl_rank": request.POST.get("jee_crl_rank"),
            "jee_category_rank": request.POST.get("jee_category_rank"),
            "annual_income": request.POST.get("annual_income"),
            "class_12_percentage": request.POST.get("class_12_percentage"),
        }
        return redirect("student_profile_documents")

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


def student_profile_documents(request):
    student_data = request.session.get("student_data")
    if not student_data:
        return redirect("common_login")

    roll_no = student_data["roll_no"]
    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    profile_data = request.session.get("student_profile_data")
    if not profile_data and profile:
        profile_data = {
            "institute_email": profile.institute_email,
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

    if not profile_data:
        return redirect("student_profile")

    if request.method == "POST":
        defaults = {
            **profile_data,
            "bank_passbook_file": request.FILES.get("bank_passbook_file") or (profile.bank_passbook_file if profile else None),
            "jee_certificate_file": request.FILES.get("jee_certificate_file") or (profile.jee_certificate_file if profile else None),
            "category_certificate_file": request.FILES.get("category_certificate_file") or (profile.category_certificate_file if profile else None),
            "income_proof_file": request.FILES.get("income_proof_file") or (profile.income_proof_file if profile else None),
            "class_12_marksheet_file": request.FILES.get("class_12_marksheet_file") or (profile.class_12_marksheet_file if profile else None),
            "fee_receipt_odd_semester_file": request.FILES.get("fee_receipt_odd_semester_file") or (profile.fee_receipt_odd_semester_file if profile else None),
            "fee_receipt_even_semester_file": request.FILES.get("fee_receipt_even_semester_file") or (profile.fee_receipt_even_semester_file if profile else None),
            "domicile_certificate_file": request.FILES.get("domicile_certificate_file") or (profile.domicile_certificate_file if profile else None),
            "no_disciplinary_action": False,
            "is_profile_complete": False,
        }
        StudentScholarshipProfile.objects.update_or_create(
            roll_no=roll_no,
            defaults=defaults,
        )
        return redirect("student_profile_save")

    return render(request, "student_profile_documents.html", {
        "student": student_data,
        "profile": profile,
        "profile_data": profile_data,
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
            messages.error(
                request,
                "You must confirm that no disciplinary action has been taken against you. If any information provided is found to be invalid, disciplinary action may be taken.",
            )
            return redirect("student_profile_save")

        profile.no_disciplinary_action = True
        profile.is_profile_complete = True
        profile.save()
        request.session.pop("student_profile_data", None)
        messages.success(request, "Profile saved successfully.")
        return redirect("eligible_scholarships")

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
        elif name == "Department":
            allowed = json.loads(value)
            print(f"Department => Student={student['department']} Allowed={allowed}")
            if student["department"] not in allowed:
                reason = f"Department criteria mismatch: '{student['department']}' is not in {allowed}."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
        elif name == "Category":
            if student["category"] != value:
                reason = f"Category criteria mismatch: expected '{value}', got '{student['category']}'."
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
        elif name == "Single Parent":
            required = value == "Yes"
            print("profile.single_parent_child: ", profile.single_parent_child)
            if profile.single_parent_child != required:
                reason = f"Single-parent criteria mismatch: required '{required}', got '{profile.single_parent_child}'."
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
        elif name == "Disciplinary Action":
            required = value == "Yes"
            student_has_disciplinary_action = not getattr(profile, "no_disciplinary_action", False)
            print(f"Disciplinary Action => Student={student_has_disciplinary_action} Required={required}")
            if student_has_disciplinary_action != required:
                reason = f"Disciplinary-action criteria mismatch: required '{required}', got '{student_has_disciplinary_action}'."
                reasons.append(reason)
                print(f"Result => NOT ELIGIBLE: {reason}")
                return False, reasons
    print(f"Result => ELIGIBLE")
    return True, reasons
            

def eligible_scholarships(request):
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

    ext = os.path.splitext(field.name)[1].lower()

    return {
        "filename": os.path.basename(field.name),
        "is_image": ext in [".jpg", ".jpeg", ".png"],
    }

def student_dashboard(request):
    email = request.session.get("email")
    if not email:
        return redirect("common_login")

    print("Email =", email)

    student = request.session.get("student_data")
    if not student or student.get("email") != email:
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

        student = {
            "roll_no": (student_api_data.get("Roll No") or "").strip(),
            "name": student_api_data.get("Name"),
            "gender": student_api_data.get("Gender"),
            "category": student_api_data.get("Category"),
            "program": student_api_data.get("prg"),
            "department": student_api_data.get("dept"),
            "batch": student_api_data.get("Current Batch"),
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
        "Pharmaceutical": "Department of Pharmaceutical Engineering",
        "Biochemical": "School of Biochemical Engineering",
        "Biomedical": "School of Biomedical Engineering",
        "Decision Science": "School of Decision Science and Engineering",
        "DSE": "School of Decision Science and Engineering",
        "Materials": "School of Materials Science and Technology",
        "MST": "School of Materials Science and Technology",
        "Chemistry": "Department of Chemistry",
        "Mathematics": "Department of Mathematical Sciences",
        "Mathematical Sciences": "Department of Mathematical Sciences",
        "Physics": "Department of Physics",
        "Humanities": "Department of Humanistic Studies",
        "Humanistic Studies": "Department of Humanistic Studies",
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
    if StudentScholarship.objects.filter(roll_no=roll_no, status="AWARDED"
    ).exists():    
        messages.warning(request,
            "You have already applied for a scholarship. Multiple applications are not permitted.")
        return redirect("student_dashboard")
    # Student has already applied for the same scholarship
    if StudentScholarship.objects.filter(roll_no=roll_no, scholarship_id=scholarship_id,
        status="APPLIED").exists():
        messages.warning(request,
            "You have already applied for this scholarship. Multiple applications are not permitted.")
        return redirect("student_dashboard")
    scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=scholarship_id,
        is_active=True)

    StudentScholarship.objects.create(roll_no=roll_no, scholarship=scholarship,
        status="APPLIED")

    messages.success(request,
        "Your scholarship application has been submitted successfully.")

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

def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _academic_session_from_date(dt_value):
    if not dt_value:
        return ""
    start_year = dt_value.year if dt_value.month >= 7 else dt_value.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


def _sanitize_filename(value):
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value))
    cleaned = cleaned.strip("_")
    return cleaned or "unknown"


def _department_code(department_name):
    text = (department_name or "").strip()
    if not text:
        return "GEN"

    manual_map = {
        "Department of Computer Science and Engineering": "CSE",
        "Department of Electrical Engineering": "EEE",
        "Department of Electronics Engineering": "ECE",
        "Department of Mechanical Engineering": "ME",
        "Department of Civil Engineering": "CE",
        "Department of Chemical Engineering and Technology": "CH",
        "Department of Mining Engineering": "MIN",
        "Department of Metallurgical Engineering": "MT",
        "Department of Ceramic Engineering": "CER",
        "Department of Architecture, Planning and Design": "ARCH",
        "School of Materials Science and Technology": "MST",
        "School of Biomedical Engineering": "BME",
        "School of Biochemical Engineering": "BCE",
        "School of Decision Science and Engineering": "DSE",
    }
    if text in manual_map:
        return manual_map[text]

    normalized = text.replace("Department of", "").replace("School of", "").strip()
    words = [w for w in normalized.replace("-", " ").split() if w.lower() not in {"and", "of", "the"}]
    initials = "".join(word[0].upper() for word in words if word and word[0].isalnum())
    if len(initials) >= 2:
        return initials[:5]
    return _sanitize_filename(normalized.upper())[:5] or "GEN"


def _get_student_snapshot(roll_no):
    student = {
        "roll_no": roll_no,
        "name": "Unknown",
        "department": "",
        "program": "",
        "batch": "",
        "category": "",
        "email": "",
        "gender": "",
        "dob": "",
        "admit_year": "",
        "spi": 0.0,
        "cpi": 0.0,
        "photo_url": "",
    }

    try:
        payload = get_student_details(roll_no)
        parsed = json.loads(payload) if payload else {}
        student.update(
            {
                "name": parsed.get("Name") or "Unknown",
                "department": parsed.get("dept") or "",
                "program": parsed.get("prg") or "",
                "batch": parsed.get("Current Batch") or "",
                "category": parsed.get("Category") or "",
                "email": parsed.get("email") or "",
                "gender": parsed.get("Gender") or "",
                "dob": parsed.get("dob") or "",
                "admit_year": parsed.get("admit_year") or "",
            }
        )
        spi_cpi = get_spi_cpi(roll_no, "2025-26-2") or {}
        student["spi"] = _safe_float(spi_cpi.get("spi"))
        student["cpi"] = _safe_float(spi_cpi.get("cpi"))
        student["photo_url"] = get_photo_url(roll_no) or ""
    except Exception as exc:
        print("application_management student lookup error:", exc)
    return student


def _student_docs(profile):
    if not profile:
        return []

    return [
        ("Bank Passbook", profile.bank_passbook_file),
        ("JEE Certificate", profile.jee_certificate_file),
        ("Category Certificate", profile.category_certificate_file),
        ("Income Proof", profile.income_proof_file),
        ("Class 12 Marksheet", profile.class_12_marksheet_file),
        ("Fee Receipt Odd Semester", profile.fee_receipt_odd_semester_file),
        ("Fee Receipt Even Semester", profile.fee_receipt_even_semester_file),
        ("Domicile Certificate", profile.domicile_certificate_file),
    ]


def _pdf_from_lines(title, lines):
    packet = BytesIO()
    pdf = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    x = 40
    y = height - 50

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(x, y, title)
    y -= 24
    pdf.setFont("Helvetica", 10)

    for line in lines:
        text = str(line)
        chunks = [text[i : i + 110] for i in range(0, len(text), 110)] or [""]
        for chunk in chunks:
            if y <= 45:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = height - 45
            pdf.drawString(x, y, chunk)
            y -= 14

    pdf.save()
    packet.seek(0)
    return packet.getvalue()


def _document_as_pdf_bytes(file_field, title):
    if not file_field:
        return None

    try:
        file_field.open("rb")
        raw = file_field.read()
    except Exception:
        return None
    finally:
        try:
            file_field.close()
        except Exception:
            pass

    filename = (file_field.name or "").lower()
    if filename.endswith(".pdf"):
        return raw

    packet = BytesIO()
    pdf = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, height - 40, title)

    try:
        img = ImageReader(BytesIO(raw))
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


def _build_student_pdf(roll_no, student, profile, applications, include_documents=False):
    lines = [
        f"Generated At: {timezone.now().strftime('%d-%m-%Y %H:%M')}",
        "",
        "Student Information",
        f"Roll Number: {roll_no}",
        f"Name: {student.get('name')}",
        f"Department: {student.get('department')}",
        f"Programme: {student.get('program')}",
        f"Semester/Batch: {student.get('batch')}",
        f"SPI: {student.get('spi')}",
        f"CPI: {student.get('cpi')}",
        f"Category: {student.get('category')}",
    ]

    if profile:
        lines.extend(
            [
                f"Annual Income: {profile.annual_income}",
                f"Mobile: {profile.mobile_number}",
                f"Email: {profile.institute_email}",
            ]
        )

    lines.extend(["", "Applied Scholarships"])
    for app in applications:
        lines.append(
            f"- {app.scholarship.scholarship_name} | Status: {app.status} | Applied On: {app.application_date.strftime('%d-%m-%Y')}"
        )

    if include_documents:
        lines.extend(["", "Uploaded Documents"])
        for label, doc_field in _student_docs(profile):
            if doc_field:
                lines.append(f"- {label}: {os.path.basename(doc_field.name)}")

    title = f"Scholarship Application {'Complete' if include_documents else 'Summary'} - {roll_no}"
    return _pdf_from_lines(title, lines)


def _build_student_documents_zip(roll_no, profile):
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipf:
        for label, file_field in _student_docs(profile):
            doc_pdf = _document_as_pdf_bytes(file_field, label)
            if doc_pdf:
                zipf.writestr(f"{_sanitize_filename(label)}.pdf", doc_pdf)
    archive.seek(0)
    return archive.getvalue()


def _build_student_bundle_zip(roll_no, student, profile, applications):
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipf:
        zipf.writestr("Summary.pdf", _build_student_pdf(roll_no, student, profile, applications, include_documents=False))
        zipf.writestr("Complete_Application.pdf", _build_student_pdf(roll_no, student, profile, applications, include_documents=True))

        for label, file_field in _student_docs(profile):
            doc_pdf = _document_as_pdf_bytes(file_field, label)
            if doc_pdf:
                zipf.writestr(f"documents/{_sanitize_filename(label)}.pdf", doc_pdf)
    archive.seek(0)
    return archive.getvalue()


def _merge_pdf_bytes(parts):
    writer = PdfWriter()
    for part in parts:
        if not part:
            continue
        try:
            reader = PdfReader(BytesIO(part))
            for page in reader.pages:
                writer.add_page(page)
        except Exception as exc:
            print("PDF merge error:", exc)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _build_student_combined_pdf(roll_no, student, profile, applications):
    scholarship_lines = [
        f"Generated At: {timezone.now().strftime('%d-%m-%Y %H:%M')}",
        f"Roll Number: {roll_no}",
        f"Name: {student.get('name') or 'Unknown'}",
        f"Department: {student.get('department') or 'Unknown'}",
        "",
        "Applied Scholarships",
    ]
    for app in applications:
        scholarship_lines.append(
            f"- {app.scholarship.scholarship_name} | Status: {app.status} | Applied On: {app.application_date.strftime('%d-%m-%Y %H:%M')}"
        )

    profile_lines = [
        "Academic Profile Information",
        f"Name: {student.get('name') or 'Unknown'}",
        f"Roll Number: {roll_no}",
        f"Department: {student.get('department') or ''}",
        f"Programme: {student.get('program') or ''}",
        f"Semester/Batch: {student.get('batch') or ''}",
        f"SPI: {student.get('spi')}",
        f"CPI: {student.get('cpi')}",
        f"Category: {student.get('category') or ''}",
        f"Gender: {student.get('gender') or ''}",
        f"Email: {student.get('email') or ''}",
        f"Date of Birth: {student.get('dob') or ''}",
        f"Admit Year: {student.get('admit_year') or ''}",
        "",
        "Scholarship Profile Form Details",
    ]

    if profile:
        profile_lines.extend(
            [
                f"Institute Email: {profile.institute_email}",
                f"Aadhaar Number: {profile.aadhaar_number}",
                f"Mobile Number: {profile.mobile_number}",
                f"Bank Name: {profile.bank_name}",
                f"Bank Branch: {profile.bank_branch}",
                f"Account Number: {profile.account_number}",
                f"IFSC Code: {profile.ifsc_code}",
                f"Single Parent Child: {'Yes' if profile.single_parent_child else 'No'}",
                f"JEE CRL Rank: {profile.jee_crl_rank}",
                f"JEE Category Rank: {profile.jee_category_rank}",
                f"Annual Income: {profile.annual_income}",
                f"Class 12 Percentage: {profile.class_12_percentage}",
                f"No Disciplinary Action Declaration: {'Yes' if profile.no_disciplinary_action else 'No'}",
                f"Profile Complete: {'Yes' if profile.is_profile_complete else 'No'}",
            ]
        )
    else:
        profile_lines.append("No scholarship profile form data found for this student.")

    merged_parts = [
        _pdf_from_lines(f"Scholarship Details - {roll_no}", scholarship_lines),
        _pdf_from_lines(f"Complete Profile - {roll_no}", profile_lines),
    ]

    for label, file_field in _student_docs(profile):
        doc_pdf = _document_as_pdf_bytes(file_field, label)
        if doc_pdf:
            merged_parts.append(doc_pdf)

    return _merge_pdf_bytes(merged_parts)


def _collect_student_rows(filters):
    applications_qs = StudentScholarship.objects.select_related("scholarship").order_by("-application_date")
    if filters["roll_no"]:
        applications_qs = applications_qs.filter(roll_no__icontains=filters["roll_no"])
    if filters["scholarship_id"]:
        applications_qs = applications_qs.filter(scholarship_id=filters["scholarship_id"])

    grouped = defaultdict(list)
    for app in applications_qs:
        grouped[app.roll_no].append(app)

    student_cache = {}
    rows = []
    departments = set()
    sessions = set()

    for roll_no, apps in grouped.items():
        if roll_no not in student_cache:
            student_cache[roll_no] = _get_student_snapshot(roll_no)
        student = student_cache[roll_no]

        latest = max(apps, key=lambda a: a.application_date)
        session = _academic_session_from_date(latest.application_date)
        sessions.add(session)
        department = student.get("department") or "Unknown"
        departments.add(department)

        if filters["department"] and department != filters["department"]:
            continue
        if filters["academic_session"] and session != filters["academic_session"]:
            continue

        statuses = {a.status for a in apps}
        aggregate_status = "PENDING"
        if "AWARDED" in statuses:
            aggregate_status = "AWARDED"
        elif statuses == {"REJECTED"}:
            aggregate_status = "REJECTED"

        if filters["status"] and aggregate_status != filters["status"]:
            continue

        rows.append(
            {
                "roll_no": roll_no,
                "name": student.get("name") or "Unknown",
                "department": department,
                "scholarships_applied": len(apps),
                "status": aggregate_status,
                "academic_session": session,
                "latest_applied_on": latest.application_date,
            }
        )

    rows.sort(key=lambda item: item["latest_applied_on"], reverse=True)
    return rows, sorted(departments), sorted(s for s in sessions if s), student_cache


def application_management(request):
    filters = {
        "roll_no": request.GET.get("roll_no", "").strip(),
        "department": request.GET.get("department", "").strip(),
        "scholarship_id": request.GET.get("scholarship", "").strip(),
        "academic_session": request.GET.get("academic_session", "").strip(),
        "status": request.GET.get("status", "").strip(),
    }

    all_rows, departments, sessions, _ = _collect_student_rows(
        {
            "roll_no": "",
            "department": "",
            "scholarship_id": "",
            "academic_session": "",
            "status": "",
        }
    )
    has_searched = request.GET.get("searched") == "1" or any(filters.values())
    rows = _collect_student_rows(filters)[0] if has_searched else []

    summary = {
        "total": len(all_rows),
        "pending": sum(1 for r in all_rows if r["status"] == "PENDING"),
        "awarded": sum(1 for r in all_rows if r["status"] == "AWARDED"),
        "rejected": sum(1 for r in all_rows if r["status"] == "REJECTED"),
    }

    return render(
        request,
        "application_management.html",
        {
            "applications": rows,
            "summary": summary,
            "departments": departments,
            "academic_sessions": sessions,
            "scholarships": ScholarshipMaster.objects.filter(is_active=True).order_by("scholarship_name"),
            "selected": filters,
            "has_searched": has_searched,
        },
    )


def application_detail(request, roll_no):
    applications = list(
        StudentScholarship.objects.filter(roll_no=roll_no).select_related("scholarship").order_by("-application_date")
    )
    if not applications:
        messages.error(request, "No scholarship applications found for the requested student.")
        return redirect("application_management")

    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    student = _get_student_snapshot(roll_no)
    documents = []
    for label, field in _student_docs(profile):
        if field:
            documents.append({"label": label, "filename": os.path.basename(field.name)})

    return render(
        request,
        "application_detail.html",
        {
            "roll_no": roll_no,
            "student": student,
            "profile": profile,
            "applications": applications,
            "documents": documents,
        },
    )


def download_application_summary_pdf(request, roll_no):
    applications = list(StudentScholarship.objects.filter(roll_no=roll_no).select_related("scholarship").order_by("-application_date"))
    if not applications:
        raise Http404("No applications found for this student.")

    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    student = _get_student_snapshot(roll_no)
    pdf_bytes = _build_student_pdf(roll_no, student, profile, applications, include_documents=False)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="summary_{_sanitize_filename(roll_no)}.pdf"'
    return response


def download_application_complete_pdf(request, roll_no):
    applications = list(StudentScholarship.objects.filter(roll_no=roll_no).select_related("scholarship").order_by("-application_date"))
    if not applications:
        raise Http404("No applications found for this student.")

    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    student = _get_student_snapshot(roll_no)
    pdf_bytes = _build_student_pdf(roll_no, student, profile, applications, include_documents=True)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="complete_{_sanitize_filename(roll_no)}.pdf"'
    return response


def download_application_documents_zip(request, roll_no):
    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if not profile:
        raise Http404("No profile documents found for this student.")

    zip_bytes = _build_student_documents_zip(roll_no, profile)
    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="documents_{_sanitize_filename(roll_no)}.zip"'
    return response


def download_application_bundle(request, roll_no):
    applications = list(StudentScholarship.objects.filter(roll_no=roll_no).select_related("scholarship").order_by("-application_date"))
    if not applications:
        raise Http404("No applications found for this student.")

    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    student = _get_student_snapshot(roll_no)
    zip_bytes = _build_student_bundle_zip(roll_no, student, profile, applications)
    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="application_{_sanitize_filename(roll_no)}.zip"'
    return response


def download_application_scope_zip(request):
    scope = request.GET.get("scope", "").strip().lower()
    roll_no = request.GET.get("roll_no", "").strip()
    department = request.GET.get("department", "").strip()
    scholarship_id = request.GET.get("scholarship", "").strip()
    academic_session = request.GET.get("academic_session", "").strip()

    if scope == "student" and not roll_no:
        messages.error(request, "Please provide a roll number for student-level download.")
        return redirect("application_management")
    if scope == "department" and not department:
        messages.error(request, "Please select a department for department-level download.")
        return redirect("application_management")

    if scope == "search":
        filters = {
            "roll_no": roll_no,
            "department": department,
            "scholarship_id": scholarship_id,
            "academic_session": academic_session,
            "status": request.GET.get("status", "").strip(),
        }
        rows, _, _, student_cache = _collect_student_rows(filters)
    else:
        filters = {
            "roll_no": roll_no if scope == "student" else "",
            "department": department if scope == "department" else "",
            "scholarship_id": scholarship_id,
            "academic_session": academic_session,
            "status": "",
        }
        rows, _, _, student_cache = _collect_student_rows(filters)

    if scope == "student" and roll_no:
        rows = [r for r in rows if r["roll_no"] == roll_no]

    if scope not in {"student", "department", "institute", "search"}:
        messages.error(request, "Invalid scope selected for download.")
        return redirect("application_management")

    if not rows:
        messages.warning(request, "No matching applications available for download.")
        return redirect("application_management")

    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipf:
        for row in rows:
            row_roll = row["roll_no"]
            apps = list(
                StudentScholarship.objects.filter(roll_no=row_roll).select_related("scholarship").order_by("-application_date")
            )
            profile = StudentScholarshipProfile.objects.filter(roll_no=row_roll).first()
            student = student_cache.get(row_roll) or _get_student_snapshot(row_roll)
            department_code = _department_code(student.get("department"))
            filename = f"{department_code}_{_sanitize_filename(row_roll)}.pdf"
            merged_pdf = _build_student_combined_pdf(row_roll, student, profile, apps)
            zipf.writestr(f"applications/{filename}", merged_pdf)

    archive.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M")
    label = scope
    if scope == "department":
        label = _sanitize_filename(department or "department")
    if scope == "student":
        label = _sanitize_filename(roll_no or "student")

    response = HttpResponse(archive.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="applications_{label}_{ts}.zip"'
    return response