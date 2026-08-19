from django.db import migrations


def create_socialapp_sites_table(apps, schema_editor):
    connection = schema_editor.connection

    table_name = "socialaccount_socialapp_sites"

    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)

        if table_name in tables:
            return

        cursor.execute(
            """
            CREATE TABLE `socialaccount_socialapp_sites` (
                `id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
                `socialapp_id` integer NOT NULL,
                `site_id` integer NOT NULL,
                CONSTRAINT
                    `socialaccount_socialapp_sites_socialapp_id_site_id_71a9a768_uniq`
                    UNIQUE (`socialapp_id`, `site_id`),
                CONSTRAINT
                    `socialaccount_social_socialapp_id_97fb6e7d_fk_socialacc`
                    FOREIGN KEY (`socialapp_id`)
                    REFERENCES `socialaccount_socialapp` (`id`),
                CONSTRAINT
                    `socialaccount_socialapp_sites_site_id_2579dee5_fk_django_site_id`
                    FOREIGN KEY (`site_id`)
                    REFERENCES `django_site` (`id`)
            )
            """
        )


def reverse_create_socialapp_sites_table(apps, schema_editor):
    connection = schema_editor.connection

    table_name = "socialaccount_socialapp_sites"

    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)

        if table_name in tables:
            cursor.execute(
                "DROP TABLE `socialaccount_socialapp_sites`"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('sch_master', '0013_studentscholarshipprofile_current_semester'),
        ("sites", "0002_alter_domain_unique"),
        ("socialaccount", "0006_alter_socialaccount_extra_data"),
    ]

    operations = [
        migrations.RunPython(
            create_socialapp_sites_table,
            reverse_create_socialapp_sites_table,
        ),
    ]
