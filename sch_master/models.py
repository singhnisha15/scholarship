from django.db import models

# Create your models here.

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