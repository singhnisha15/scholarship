from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    StudentScholarship = apps.get_model('sch_master', 'StudentScholarship')
    StudentScholarshipAward = apps.get_model('sch_master', 'StudentScholarshipAward')
    from django.utils import timezone

    for application in StudentScholarship.objects.all():
        decision_date = getattr(application, 'decision_date', None)
        if application.status == 'AWARDED' or decision_date is not None:
            StudentScholarshipAward.objects.create(
                student_scholarship=application,
                decision_date=decision_date or timezone.now(),
            )


def backwards(apps, schema_editor):
    StudentScholarship = apps.get_model('sch_master', 'StudentScholarship')
    StudentScholarshipAward = apps.get_model('sch_master', 'StudentScholarshipAward')

    for award in StudentScholarshipAward.objects.all():
        application = award.student_scholarship
        application.decision_date = award.decision_date
        application.save()


class Migration(migrations.Migration):

    dependencies = [
        ('sch_master', '0008_correct_scholarship_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentScholarshipAward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('decision_date', models.DateTimeField()),
                ('awarded_by', models.CharField(blank=True, max_length=200, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student_scholarship', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='award', to='sch_master.studentscholarship')),
            ],
            options={
                'db_table': 'student_scholarship_award',
            },
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name='studentscholarship',
            name='decision_date',
        ),
    ]
