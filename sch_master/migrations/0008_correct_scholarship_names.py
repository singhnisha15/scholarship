from django.db import migrations


def correct_scholarship_names(apps, schema_editor):
    ScholarshipMaster = apps.get_model("sch_master", "ScholarshipMaster")

    # Remove "/" from scholarship names
    for s in ScholarshipMaster.objects.filter(scholarship_name__contains="/"):
        s.scholarship_name = s.scholarship_name.replace("/", "")
        s.save(update_fields=["scholarship_name"])

    # Fix Aditya scholarship
    ScholarshipMaster.objects.filter(
        scholarship_name="�Aditya Gupta Endowment Scholarship (MET) for Metallurgical Engineering Students�."
    ).update(
        scholarship_name="Aditya Gupta Endowment Scholarship (MET) for Metallurgical Engineering Students"
    )

    # Fix Rupa Rahul Bajaj scholarship
    ScholarshipMaster.objects.filter(
        scholarship_name="Rupa Rahul Bajaj Scholarship for Women in Engineering(RRBSWE)."
    ).update(
        scholarship_name="Rupa Rahul Bajaj Scholarship for Women in Engineering(RRBSWE)"
    )

    # Fix D.N. Bhargava scholarship
    ScholarshipMaster.objects.filter(
        scholarship_name="D.N. Bhargava FellowshipScholarship AwardMedals for the Department of Mining Engineering."
    ).update(
        scholarship_name="D.N. Bhargava Fellowship"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sch_master", "0007_studentscholarshipprofile_class_12_marksheet_file_and_more"),   # <-- replace with your actual previous migration
    ]

    operations = [
        migrations.RunPython(correct_scholarship_names),
    ]