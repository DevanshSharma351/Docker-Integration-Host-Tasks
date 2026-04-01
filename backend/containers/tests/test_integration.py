import pytest
import docker

# This marker means these tests only run when you
# explicitly pass --integration flag
# Run with: pytest --integration -v
# Normal run skips these automatically


@pytest.fixture(scope='module')
def docker_client():
    """Real Docker client — requires daemon running."""
    try:
        client = docker.DockerClient(
            base_url='unix:///var/run/docker.sock'
        )
        client.ping()
        return client
    except Exception:
        pytest.skip('Docker daemon not reachable')


@pytest.fixture
def host(db):
    from containers.models import Host
    return Host.objects.create(
        name='local-integration',
        ip_address='127.0.0.1',
        port=2375
    )


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='integration_user',
        password='pass'
    )


@pytest.mark.integration
class TestRealDockerLifecycle:
    """
    These tests spin up real containers.
    Requires Docker daemon running locally.
    Each test cleans up after itself.
    """

    def test_create_and_remove_container(
        self, db, docker_client, host, user
    ):
        from containers import services

        # Create
        record, error = services.create_container(
            host=host,
            user=user,
            image_ref='nginx:alpine',
            name='integration-test-nginx',
            environment={},
            port_bindings={},
            volumes=[],
        )

        assert error is None
        assert record is not None
        assert record.status == 'RUNNING'

        # Verify it actually exists on the daemon
        sdk_container = docker_client.containers.get(record.container_id)
        assert sdk_container.status == 'running'

        # Clean up — remove it
        remove_error = services.remove_container(record, user)
        assert remove_error is None
        record.refresh_from_db()
        assert record.status == 'REMOVED'

    def test_stop_and_start(self, db, docker_client, host, user):
        from containers import services

        record, _ = services.create_container(
            host=host, user=user,
            image_ref='nginx:alpine',
            name='integration-test-stop',
            environment={}, port_bindings={}, volumes=[],
        )

        # Stop it
        error = services.lifecycle_action(record, user, 'stop')
        assert error is None
        record.refresh_from_db()
        assert record.status == 'STOPPED'

        # Verify on daemon
        sdk_container = docker_client.containers.get(record.container_id)
        assert sdk_container.status == 'exited'

        # Clean up
        services.remove_container(record, user)

    def test_real_stats_shape(self, db, docker_client, host, user):
        from containers import services

        record, _ = services.create_container(
            host=host, user=user,
            image_ref='nginx:alpine',
            name='integration-test-stats',
            environment={}, port_bindings={}, volumes=[],
        )

        stats, error = services.get_container_stats(record)

        assert error is None
        # Verify the real Docker response has the shape we expect
        assert 'cpu_percent' in stats
        assert 'memory' in stats
        assert 'usage_bytes' in stats['memory']
        assert 'limit_bytes' in stats['memory']
        assert 'network' in stats
        assert 'block_io' in stats

        # Clean up
        services.remove_container(record, user)

    def test_real_logs(self, db, docker_client, host, user):
        from containers import services
        import time

        record, _ = services.create_container(
            host=host, user=user,
            image_ref='nginx:alpine',
            name='integration-test-logs',
            environment={}, port_bindings={}, volumes=[],
        )

        time.sleep(1)  # give nginx a second to write startup logs
        lines, error = services.get_container_logs(record, tail=50)

        assert error is None
        assert isinstance(lines, list)
        assert len(lines) > 0  # nginx always logs on startup

        services.remove_container(record, user)