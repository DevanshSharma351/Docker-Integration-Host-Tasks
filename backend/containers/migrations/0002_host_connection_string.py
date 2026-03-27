from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('containers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='host',
            name='connection_string',
            field=models.CharField(
                default='unix:///var/run/docker.sock',
                help_text='Docker daemon address, e.g. unix:///var/run/docker.sock or tcp://127.0.0.1:2375',
                max_length=255,
            ),
        ),
    ]
