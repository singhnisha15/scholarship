import json
from datetime import datetime
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .services.academic_api import get_student_details, get_photo_url
import pandas as pd
from .models import ScholarshipMaster, CriteriaMaster, ScholarshipCriteria, StudentScholarshipProfile, StudentScholarship
from django.utils import timezone

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

def student_login(request):
    return render(request, "student_login.html")

def google_login(request):

    email = "nishasingh.rs.cse21@itbhu.ac.in"      #nishasingh.rs.cse21@itbhu.ac.in Change to request.user.email in production or nishasingh.rs.cse21@itbhu.ac.in
    request.session["email"] = email

    office_users = [
        "ar.sch@itbhu.ac.in",
        "office.sch@itbhu.ac.in",
        "nisha.cis@itbhu.ac.in",
    ]

    if email.lower() in office_users:
        return redirect("scholarship_dashboard")

    return redirect("student_dashboard")

def student_profile(request):
    student_data = request.session.get("student_data")
    roll_no = student_data["roll_no"]
    existing_award = StudentScholarship.objects.filter(roll_no=roll_no, status='ACTIVE')
    if existing_award.exists():
        return render(request, "already_awarded.html", {"awards": existing_award, "student": student_data})
    profile = StudentScholarshipProfile.objects.filter(roll_no=roll_no).first()
    if profile and profile.is_profile_complete:
        return redirect("eligible_scholarships")
    return render(request, "student_profile.html", {"student": student_data, "profile": profile})

def student_profile_save(request):
    if request.method != "POST": return redirect("student_dashboard")
    student_data = request.session["student_data"]
    StudentScholarshipProfile.objects.update_or_create(
        roll_no=student_data["roll_no"],
        defaults={
            "institute_email": student_data["email"],
            "aadhaar_number": request.POST.get("aadhaar_number"),
            "bank_name": request.POST.get("bank_name"),
            "bank_branch": request.POST.get("bank_branch"),
            "account_number": request.POST.get("account_number"),
            "ifsc_code": request.POST.get("ifsc_code"),
            "mobile_number": request.POST.get("mobile_number"),
            "single_parent_child": request.POST.get("single_parent_child") == "Yes",
            "jee_advance_rank": request.POST.get("jee_advance_rank"),
            "jee_crl_rank": request.POST.get("jee_crl_rank"),
            "jee_category_rank": request.POST.get("jee_category_rank"),
            "annual_income": request.POST.get("annual_income"),
            "bank_passbook_file": request.FILES.get("bank_passbook_file"),
            "jee_certificate_file": request.FILES.get("jee_certificate_file"),
            "category_certificate_file": request.FILES.get("category_certificate_file"),
            "income_proof_file": request.FILES.get("income_proof_file"),
            "is_profile_complete": True,
        },
    )
    return redirect("eligible_scholarships")

def is_scholarship_eligible(scholarship, student, profile):
    print("\n")
    print("=" * 80)
    print(f"Checking Scholarship : {scholarship.scholarship_name}")
    print(f"Student : {student['name']}")
    print("=" * 80)
    for criterion in scholarship.criteria.all():
        name = criterion.criteria.criteria_name
        print(f"Evaluating Criterion: {name}")
        value = criterion.criteria_value
        if name == "Gender":
            print(f"Gender => Student={student['gender']} Required={value}")
            if student["gender"] != value: return False
        elif name == "Program":
            allowed = json.loads(value)
            print(f"Program => Student={student['program']} Allowed={allowed}")
            if student["program"] not in allowed: return False
        elif name == "Department":
            allowed = json.loads(value)
            print(f"Department => Student={student['department']} Allowed={allowed}")
            if student["department"] not in allowed: return False
        elif name == "Category":
            if student["category"] != value: return False
        elif name == "Income":
            print(f"Income => Student={profile.annual_income} Limit={value}")
            if float(profile.annual_income) >= float(value): return False
        elif name == "Single Parent":
            required = value == "Yes"
            print("profile.single_parent_child: ", profile.single_parent_child)
            if profile.single_parent_child != required: return False
        elif name == "Age":
            dob = datetime.strptime(student["dob"], "%d-%m-%Y")
            age = datetime.today().year - dob.year
            age_limit = int(float(value))
            print(f"Age => Student={age} Limit={value}")
            if age >= age_limit: return False
    return True

def eligible_scholarships(request):
    student = request.session.get("student_data")
    if not student: return redirect("student_login")
    profile = StudentScholarshipProfile.objects.get(roll_no=student["roll_no"])
    scholarships = ScholarshipMaster.objects.filter(is_active=True)
    eligible = [sch for sch in scholarships if is_scholarship_eligible(sch, student, profile)]
    return render(request, "eligible_scholarships.html", {"student": student, "scholarships": eligible})

def student_dashboard(request):
    email = request.session.get("email")
    print("Email =", email)
    student = get_student_details(email)
    print(type(student)); print(student)
    if not email: return redirect("student_login")
    student = json.loads(student)
    student = {
        "roll_no": student.get("Roll No"),
        "name": student.get("Name"),
        "gender": student.get("Gender"),
        "category": student.get("Category"),
        "program": student.get("prg"),
        "department": student.get("dept"),
        "batch": student.get("Current Batch"),
        "email": student.get("email"),
        "contact_no": student.get("contact_no"),
        "admit_year": student.get("admit_year"),
        "dob": student.get("dob"),
    }
    print("student =", student); print("keys =", student.keys())
    student["photo_url"] = "/static/images/Nisha_photo.jpg"
    request.session["student_data"] = student
    student_scholarship = StudentScholarship.objects.filter(roll_no=student["roll_no"]).exclude(status="REJECTED").first()
    profile = StudentScholarshipProfile.objects.filter(roll_no=student["roll_no"]).first()
    profile_completed = profile.is_profile_complete if profile else False
    return render(request, "student_dashboard.html", {"student": student, "student_scholarship": student_scholarship, "profile": profile, "profile_completed": profile_completed})

def scholarship_detail(request, scholarship_id):
    scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=scholarship_id)
    return render(request, "scholarship_detail.html", {"scholarship": scholarship})

def bulk_upload_scholarships(request):
    if request.method == "GET": return render(request, "bulk_upload_scholarships.html")
    file = request.FILES["file"]
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    criteria_lookup = {c.criteria_name: c for c in CriteriaMaster.objects.all()}
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
        "Grade (Not in)": "Failed Grade",
        "Age (<)": "Age",
        "Credits Complete (Yes/No)": "Credits Complete",
        "Single Parent (Yes/No)": "Single Parent",
        "Diciplinary Action (Yes/No)": "Disciplinary Action",
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
            criteria = criteria_lookup.get(criteria_name)
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
        return redirect("student_login")

    roll_no = student["roll_no"]

    # Student has already applied for any scholarship
    if StudentScholarship.objects.filter(roll_no=roll_no
    ).exclude(status="REJECTED").exists():

        messages.warning(request,
            "You have already applied for a scholarship. Multiple applications are not permitted.")
        return redirect("student_dashboard")

    scholarship = get_object_or_404(ScholarshipMaster, scholarship_id=scholarship_id,
        is_active=True)

    StudentScholarship.objects.create(roll_no=roll_no, scholarship=scholarship,
        status="APPLIED", award_year=timezone.now().year)

    messages.success(request,
        "Your scholarship application has been submitted successfully.")

    return redirect("student_dashboard")
