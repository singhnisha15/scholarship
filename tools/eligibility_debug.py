import os, sys
# Ensure project root is on sys.path so Django settings can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.join(__file__, '..'))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scholarship.settings')
import django
django.setup()

from sch_master.models import StudentScholarshipProfile, ScholarshipMaster
from sch_master.services.academic_api import get_student_details, get_spi_cpi
import json, hashlib
from datetime import datetime


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def student_from_api(email):
    payload = get_student_details(email)
    if not payload:
        return None, 'No API payload'
    try:
        data = json.loads(payload)
    except Exception as e:
        return None, f'API JSON parse error: {e}'
    try:
        spi_data = get_spi_cpi(data.get('Roll No'), '2026-27-1')
    except Exception as e:
        spi_data = {}
    student = {
        'roll_no': (data.get('Roll No') or '').strip(),
        'name': data.get('Name'),
        'gender': data.get('Gender'),
        'category': data.get('Category'),
        'program': data.get('prg'),
        'department': data.get('dept'),
        'batch': data.get('Current Batch'),
        'email': (data.get('email') or '').strip(),
        'contact_no': data.get('contact_no'),
        'admit_year': data.get('admit_year'),
        'dob': data.get('dob'),
        'spi': parse_float(spi_data.get('spi')),
        'cpi': parse_float(spi_data.get('cpi')),
        'credits_earned': parse_float(spi_data.get('percent_credits_earned')),
        'pass_status': data.get('pass_status'),
    }
    return student, None


def check_eligibility(student, profile, scholarship):
    # replicate checks and return (True, None) or (False, reason)
    from sch_master.models import CriteriaMaster
    for criterion in scholarship.criteria.all():
        name = CriteriaMaster.normalize_criteria_name(criterion.criteria.criteria_name)
        value = criterion.criteria_value
        if name == 'Gender':
            if student.get('gender') != value:
                return False, f'Gender mismatch: student {student.get("gender")} != required {value}'
        elif name == 'Program':
            allowed = json.loads(value)
            if student.get('program') not in allowed:
                return False, f'Program {student.get("program")} not in allowed {allowed}'
        elif name == 'Department':
            allowed = json.loads(value)
            if student.get('department') not in allowed:
                return False, f'Department {student.get("department")} not in allowed {allowed}'
        elif name == 'Category':
            if student.get('category') != value:
                return False, f'Category {student.get("category")} != {value}'
        elif name == 'Income':
            try:
                if float(profile.annual_income) >= float(value):
                    return False, f'Income {profile.annual_income} >= limit {value}'
            except Exception as e:
                return False, f'Income check error: {e}'
        elif name == 'Single Parent':
            required = value == 'Yes'
            if profile.single_parent_child != required:
                return False, f'Single parent requirement {required} not met (profile {profile.single_parent_child})'
        elif name == 'Age':
            try:
                dob = datetime.strptime(student.get('dob',''), '%d-%m-%Y')
                age = datetime.today().year - dob.year
                age_limit = int(float(value))
                if age >= age_limit:
                    return False, f'Age {age} >= limit {age_limit}'
            except Exception as e:
                return False, f'Age parse error: {e}'
        elif name == 'SPI':
            required_spi = float(value)
            if student.get('spi',0) < required_spi:
                return False, f'SPI {student.get("spi")}" < required {required_spi}'
        elif name == 'CPI':
            required_cpi = float(value)
            if student.get('cpi',0) < required_cpi:
                return False, f'CPI {student.get("cpi")} < required {required_cpi}'
        elif name == 'Credits Complete':
            required = value == 'Yes'
            has_completed_credits = student.get('credits_earned',0) >= 100
            if has_completed_credits != required:
                return False, f'Credits complete required={required} but student={has_completed_credits} (credits={student.get("credits_earned")})'
        elif name in {'Has Failed Grade','Pass Status'}:
            required = value == 'Yes'
            pass_status = str(student.get('pass_status','')).strip().lower()
            student_has_failed_grade = pass_status not in {'yes','y','true','1','pass','passed','passed with grace','promoted','clear'}
            if student_has_failed_grade != required:
                return False, f'Failed grade requirement={required} but student_has_failed_grade={student_has_failed_grade} (pass_status={student.get("pass_status")})'
        elif name == 'Disciplinary Action':
            required = value == 'Yes'
            student_has_disciplinary_action = not getattr(profile, 'no_disciplinary_action', False)
            if student_has_disciplinary_action != required:
                return False, f'Disciplinary action required={required} but student_has_disciplinary_action={student_has_disciplinary_action}'
    return True, None


if __name__ == '__main__':
    profiles = list(StudentScholarshipProfile.objects.all()[:3])
    if not profiles:
        print('No student profiles found in DB')
    else:
        scholarships = list(ScholarshipMaster.objects.filter(is_active=True))
        print('Total active scholarships:', len(scholarships))
        for p in profiles:
            print('\nProfile:', p.roll_no, p.institute_email)
            student, err = student_from_api(p.institute_email)
            if err:
                print('API error for', p.institute_email, err)
                # try to build minimal student dict from profile if API fails
                student = {'roll_no': p.roll_no, 'name':'', 'gender':'', 'category':'', 'program':'', 'department':'', 'batch':'', 'email':p.institute_email, 'contact_no':'', 'admit_year':'', 'dob':'', 'spi':0.0, 'cpi':0.0, 'credits_earned':0.0, 'pass_status':''}
            eligible = []
            ineligible = []
            for sch in scholarships:
                ok, reason = check_eligibility(student, p, sch)
                if ok:
                    eligible.append(sch.scholarship_name)
                else:
                    ineligible.append((sch.scholarship_name, reason))
            print('Eligible count:', len(eligible))
            for name in eligible[:20]:
                print('  OK:', name)
            print('--- Ineligible reasons (sample 10) ---')
            for name, reason in ineligible[:10]:
                print('  X:', name, '=>', reason)
