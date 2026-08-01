from django.urls import path

from sch_master import views
from .views import scholarship_create

urlpatterns = [
    path("create/", scholarship_create, name="scholarship_create"),
    path("google_login/", views.google_login, name="google_login"),
    path("login/", views.common_login, name="common_login"),
    path("", views.common_login, name="common_login"),
    path("student/login/", views.common_login, name="common_login"),
    path("scholarship/login/", views.common_login, name="common_login"),
    path("scholarship/bulk-upload/template/", views.download_bulk_upload_template, name="download_bulk_upload_template"),
    path("scholarship/bulk-upload/", views.bulk_upload_scholarships, name="bulk_upload_scholarships"),
    path("student/profile/", views.student_profile, name="student_profile"),
    path("student/profile/documents/", views.student_profile_documents, name="student_profile_documents"),
    path("student/profile/submit/", views.student_profile_save, name="student_profile_submit"),
    path("student/profile/save/", views.student_profile_save, name="student_profile_save"),
    path("student/eligible-scholarships/", views.eligible_scholarships, name="eligible_scholarships"),
    path(
        "student/scholarship/<int:scholarship_id>/",
        views.scholarship_detail,
        name="scholarship_detail",
    ),
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("scholarship/dashboard/", views.scholarship_dashboard, name="scholarship_dashboard"),
    path("scholarship/apply/<int:scholarship_id>/", views.apply_scholarship, name="apply_scholarship"),
    path("scholarship/assign/", views.assign_scholarship, name="assign_scholarship"),
    path("scholarship/manage/", views.manage_scholarships, name="manage_scholarships"),
    path("scholarship/view/<int:pk>/", views.view_scholarship, name="view_scholarship"),
    path("scholarship/edit/<int:pk>/", views.edit_scholarship, name="edit_scholarship"),
    path("scholarship/delete/<int:pk>/", views.delete_scholarship, name="delete_scholarship"),
    path("student/profile/edit/", views.edit_student_profile, name="edit_student_profile"),
    path("scholarship/award-bulk/",views.bulk_award_scholarships,name="bulk_award_scholarships",),
    path("scholarship/award-bulk/template/", views.download_award_template,name="download_award_template",),
    path(
        "remove_application/<int:application_id>/",
        views.remove_scholarship_application,
        name="remove_scholarship_application",
    ),   
    ]
