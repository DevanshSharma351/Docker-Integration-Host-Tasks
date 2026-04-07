from django.db import migrations, models


def dedupe_hosts(apps, schema_editor):
    Host = apps.get_model('hosts', 'Host')
    UserHostRole = apps.get_model('hosts', 'UserHostRole')
    ImagePullJob = apps.get_model('images', 'ImagePullJob')
    ImagePushJob = apps.get_model('images', 'ImagePushJob')
    ImageDeleteJob = apps.get_model('images', 'ImageDeleteJob')

    role_rank = {
        'VIEWER': 1,
        'HOST_OWNER': 2,
        'ADMIN': 3,
    }

    keep_by_endpoint = {}

    for host in Host.objects.all().order_by('created_at', 'id'):
        key = (host.ip_address, host.port)
        keep = keep_by_endpoint.get(key)
        if keep is None:
            keep_by_endpoint[key] = host
            continue

        # Re-point role mappings to the kept host, merging conflicts safely.
        for assignment in UserHostRole.objects.filter(host=host):
            existing = UserHostRole.objects.filter(
                user=assignment.user,
                host=keep,
            ).first()
            if existing:
                existing_rank = role_rank.get(existing.role, 0)
                incoming_rank = role_rank.get(assignment.role, 0)
                if incoming_rank > existing_rank:
                    existing.role = assignment.role
                    existing.assigned_by = assignment.assigned_by
                    existing.save(update_fields=['role', 'assigned_by'])
                assignment.delete()
            else:
                assignment.host = keep
                assignment.save(update_fields=['host'])

        ImagePullJob.objects.filter(host=host).update(host=keep)
        ImagePushJob.objects.filter(host=host).update(host=keep)
        ImageDeleteJob.objects.filter(host=host).update(host=keep)

        host.delete()


def noop_reverse(apps, schema_editor):
    # Duplicate rows cannot be reconstructed automatically.
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('hosts', '0002_alter_host_ssh_credentials'),
        ('images', '0002_add_push_delete_jobs'),
    ]

    operations = [
        migrations.RunPython(dedupe_hosts, noop_reverse),
        migrations.AddConstraint(
            model_name='host',
            constraint=models.UniqueConstraint(
                fields=('ip_address', 'port'),
                name='uniq_host_ip_port',
            ),
        ),
    ]
