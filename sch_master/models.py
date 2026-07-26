from django.db import models

class ScholarshipMaster(models.Model):

    scholarship_id = models.AutoField(
        primary_key=True
    )

    scholarship_name = models.CharField(
        max_length=500
    )

    description = models.TextField(
        blank=True,
        null=True,
        help_text="Terms, conditions, eligibility criteria, award rules, and any other scholarship details."
    )

    no_of_scholarships = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Number of scholarships/awards available."
    )

    scholarship_amount = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Amount and payment details as specified in the scholarship document."
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "scholarship_master"
        verbose_name = "Scholarship Master"
        verbose_name_plural = "Scholarship Master"

    def __str__(self):
        return self.scholarship_name
    
class CriteriaMaster(models.Model):

    DATA_TYPE_CHOICES = (
        ('STRING', 'String'),
        ('NUMBER', 'Number'),
        ('BOOLEAN', 'Boolean'),
        ('LIST', 'List'),
    )

    criteria_id = models.AutoField(primary_key=True)

    criteria_name = models.CharField(
        max_length=100,
        unique=True
    )

    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES
    )

    allowed_operator = models.CharField(
        max_length=20
    )

    allowed_values = models.JSONField(
        blank=True,
        null=True,
        help_text="Applicable only for LIST type criteria"
    )

    display_order = models.PositiveIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "criteria_master"
        ordering = ['display_order']

    @classmethod
    def normalize_criteria_name(cls, name):
        aliases = {
            "Pass Status": "Has Failed Grade",
            "Failed Grade": "Has Failed Grade",
            "Diciplinary Action": "Disciplinary Action",
            "Diciplinary Action (Yes/No)": "Disciplinary Action",
        }
        if not name:
            return name
        return aliases.get(name, name)

    def __str__(self):
        return self.criteria_name    


class ScholarshipCriteria(models.Model):

    scholarship = models.ForeignKey(
        ScholarshipMaster,
        on_delete=models.CASCADE,
        related_name='criteria'
    )

    criteria = models.ForeignKey(
        CriteriaMaster,
        on_delete=models.PROTECT
    )

    operator = models.CharField(
        max_length=20
    )

    criteria_value = models.TextField(
        help_text="Selected value(s) for this scholarship criterion"
    )

    class Meta:
        db_table = "scholarship_criteria"

class StudentScholarshipProfile(models.Model):

    roll_no = models.CharField(
        max_length=20,
        unique=True
    )

    institute_email = models.EmailField()

    aadhaar_number = models.CharField(
        max_length=12
    )

    bank_name = models.CharField(
        max_length=200
    )

    bank_branch = models.CharField(
        max_length=200
    )

    account_number = models.CharField(
        max_length=50
    )

    ifsc_code = models.CharField(
        max_length=20
    )

    mobile_number = models.CharField(
        max_length=15
    )

    single_parent_child = models.BooleanField(
        default=False
    )

    jee_advance_rank = models.IntegerField(
        null=True,
        blank=True
    )

    jee_crl_rank = models.IntegerField(
        null=True,
        blank=True
    )

    jee_category_rank = models.IntegerField(
        null=True,
        blank=True
    )

    annual_income = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    bank_passbook_file = models.FileField(
        upload_to='documents/passbook/'
    )

    jee_certificate_file = models.FileField(
        upload_to='documents/jee/'
    )

    category_certificate_file = models.FileField(
        upload_to='documents/category/',
        blank=True,
        null=True
    )

    income_proof_file = models.FileField(
        upload_to='documents/income/'
    )

    fee_receipt_file = models.FileField(
        upload_to='documents/fee/',
        blank=True,
        null=True
    )

    domicile_certificate_file = models.FileField(
        upload_to='documents/domicile/',
        blank=True,
        null=True
    )

    no_disciplinary_action = models.BooleanField(
        default=False
    )

    is_profile_complete = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "student_scholarship_profile"


class StudentScholarship(models.Model):

    STATUS_CHOICES = (
        ('APPLIED', 'Applied'),
        ('UNDER_REVIEW', 'Under Review'),
        ('RECOMMENDED', 'Recommended'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('AWARDED', 'Awarded'),
        ('CANCELLED', 'Cancelled'),
    )

    roll_no = models.CharField(
        max_length=20
    )

    scholarship = models.ForeignKey(
        ScholarshipMaster,
        on_delete=models.CASCADE
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='APPLIED'
    )

    application_date = models.DateTimeField(
        auto_now_add=True
    )

    decision_date = models.DateTimeField(
        null=True,
        blank=True
    )

    award_year = models.IntegerField(
        null=True,
        blank=True
    )

    remarks = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "student_scholarship"