from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib import messages
from django.shortcuts import redirect
import json

from .services.academic_api import get_student_details

def normalize_institute_email(email):
    email = (email or "").strip().lower()
    if email.endswith("@itbhu.ac.in"): return email[:-len("@itbhu.ac.in")] + "@iitbhu.ac.in"
    return email


class ScholarshipSocialAccountAdapter(DefaultSocialAccountAdapter):

    STAFF_EMAILS = {
        "ar.sch@iitbhu.ac.in",
        "office.sch@iitbhu.ac.in",
        "nisha.cis@iitbhu.ac.in",
        "paramshivay.scc@iitbhu.ac.in"
    }

    def pre_social_login(self, request, sociallogin):
        print("========== PRE SOCIAL LOGIN START ==========", flush=True)

        # Get and normalize Google email
        google_email = normalize_institute_email(
            sociallogin.user.email or sociallogin.account.extra_data.get("email", "")
        )
        print("Google email:", google_email, flush=True)

        if not google_email:
            messages.error(request, "Google did not provide a valid email address.")
            raise ImmediateHttpResponse(redirect("common_login"))

        # STAFF LOGIN
        if google_email in self.STAFF_EMAILS:
            print("STAFF LOGIN VERIFIED:", google_email, flush=True)
            request.session.update({
                "email": google_email,
                "user_type": "staff",
                "home_url": "scholarship_dashboard",
            })
            print("Staff login verification successful.", flush=True)
            return

        # STUDENT LOGIN
        try:
            student_payload = get_student_details(google_email)
            if not student_payload or not student_payload.strip():
                messages.error(request, "Your student details could not be retrieved from the academic server.")
                raise ImmediateHttpResponse(redirect("common_login"))
            student_api_data = json.loads(student_payload)
        except ImmediateHttpResponse:
            raise
        except Exception as exc:
            print("Academic API authentication error:", exc, flush=True)
            messages.error(request, "Unable to verify your student details with the academic server. Please try again later.")
            raise ImmediateHttpResponse(redirect("common_login"))

        # Verify API status
        api_status = str(student_api_data.get("status", "")).strip().lower()
        if api_status != "ok":
            print("Student login rejected: API status =", api_status, flush=True)
            messages.error(request, "Your student record could not be verified. Please contact the scholarship office.")
            raise ImmediateHttpResponse(redirect("common_login"))

        # Verify API email matches Google email
        api_email = normalize_institute_email(student_api_data.get("email", ""))
        if not api_email:
            messages.error(request, "The academic server did not return a student email.")
            raise ImmediateHttpResponse(redirect("common_login"))

        if api_email != google_email:
            print(f"Student login rejected: Google={google_email}, API={api_email}", flush=True)
            messages.error(request, "The Google account does not match the student record maintained by the academic server.")
            raise ImmediateHttpResponse(redirect("common_login"))

        # Student verified
        request.session.update({
            "email": google_email,
            "user_type": "student",
            "academic_api_data": student_api_data,
            "home_url": "student_dashboard",
        })
        print("Student login verification successful:", google_email, flush=True)
        print("========== PRE SOCIAL LOGIN END ==========", flush=True)
        return