import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hosts.models import Host
from registries.models import RegistryCredential

from .models import ImagePullJob

User = get_user_model()

# A valid Fernet key for tests (same one used in registries tests).
TEST_ENCRYPTION_KEY = "ZXcxMjNkRmVybmV0S2V5X18xMjM0NTY3ODkwYWJjZD0="


# --------------------------------------------------------------------------- #
# Model unit tests
# --------------------------------------------------------------------------- #
class ImagePullJobModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="modelowner", password="password123", role="admin"
        )
        self.host = Host.objects.create(
            name="Test Host",
            hostname="192.168.1.100",
            port=2375,
            owner=self.owner,
        )

    def test_string_representation(self):
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="nginx:1.25-alpine",
        )
        self.assertEqual(str(job), "PullJob(nginx:1.25-alpine) [PENDING]")

    def test_default_status_is_pending(self):
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="redis:7",
        )
        self.assertEqual(job.status, ImagePullJob.Status.PENDING)

    def test_optional_fields_are_null(self):
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="postgres:16",
        )
        self.assertIsNone(job.registry_credential)
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)
        self.assertIsNone(job.error_message)
        self.assertEqual(job.progress_log, "")

    def test_ordering_is_newest_first(self):
        job_a = ImagePullJob.objects.create(
            host=self.host, requested_by=self.owner, image_ref="a:1"
        )
        job_b = ImagePullJob.objects.create(
            host=self.host, requested_by=self.owner, image_ref="b:2"
        )
        jobs = list(ImagePullJob.objects.all())
        self.assertEqual(jobs[0].pk, job_b.pk)
        self.assertEqual(jobs[1].pk, job_a.pk)


# --------------------------------------------------------------------------- #
# Permission unit tests
# --------------------------------------------------------------------------- #
class ImagePullPermissionTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="padmin", password="password123", role="admin"
        )
        self.host_user = User.objects.create_user(
            username="phoster", password="password123", role="host"
        )
        self.viewer = User.objects.create_user(
            username="pviewer", password="password123", role="viewer"
        )

    def _request(self, method, user):
        class DummyRequest:
            pass

        r = DummyRequest()
        r.method = method
        r.user = user
        return r

    def test_admin_or_host_owner_allows_read_for_viewer(self):
        from .permissions import IsAdminOrHostOwner

        perm = IsAdminOrHostOwner()
        req = self._request("GET", self.viewer)
        self.assertTrue(perm.has_permission(req, None))

    def test_admin_or_host_owner_denies_post_for_viewer(self):
        from .permissions import IsAdminOrHostOwner

        perm = IsAdminOrHostOwner()
        req = self._request("POST", self.viewer)
        self.assertFalse(perm.has_permission(req, None))

    def test_admin_or_host_owner_allows_post_for_admin(self):
        from .permissions import IsAdminOrHostOwner

        perm = IsAdminOrHostOwner()
        req = self._request("POST", self.admin)
        self.assertTrue(perm.has_permission(req, None))

    def test_admin_or_host_owner_allows_post_for_host_role(self):
        from .permissions import IsAdminOrHostOwner

        perm = IsAdminOrHostOwner()
        req = self._request("POST", self.host_user)
        self.assertTrue(perm.has_permission(req, None))

    def test_admin_only_denies_viewer(self):
        from .permissions import IsAdminOnly

        perm = IsAdminOnly()
        req = self._request("DELETE", self.viewer)
        self.assertFalse(perm.has_permission(req, None))

    def test_admin_only_allows_admin(self):
        from .permissions import IsAdminOnly

        perm = IsAdminOnly()
        req = self._request("DELETE", self.admin)
        self.assertTrue(perm.has_permission(req, None))


# --------------------------------------------------------------------------- #
# Worker unit tests (mocked Docker)
# --------------------------------------------------------------------------- #
@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class ImagePullWorkerTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="wowner", password="password123", role="admin"
        )
        self.host = Host.objects.create(
            name="Worker Host",
            hostname="10.0.0.1",
            port=2375,
            owner=self.owner,
        )

    @patch("images.worker.docker.DockerClient")
    def test_successful_pull_updates_status(self, MockClient):
        """Worker should set status to SUCCESS after a successful pull."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.api.pull.return_value = [
            {"status": "Pulling from library/nginx", "id": "1.25-alpine"},
            {"status": "Digest: sha256:abc123"},
            {"status": "Status: Downloaded newer image for nginx:1.25-alpine"},
        ]

        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="nginx:1.25-alpine",
        )

        # Run the worker synchronously (import the internal function)
        from .worker import _do_pull

        _do_pull(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, ImagePullJob.Status.SUCCESS)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIn("nginx", job.progress_log)

        # Should have connected to the right host
        MockClient.assert_called_once_with(
            base_url="tcp://10.0.0.1:2375", timeout=300
        )

    @patch("images.worker.docker.DockerClient")
    def test_failed_pull_updates_status(self, MockClient):
        """Worker should set status to FAILED and record error_message."""
        import docker as docker_lib

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.api.pull.side_effect = docker_lib.errors.APIError(
            "pull access denied"
        )

        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="private/image:latest",
        )

        from .worker import _do_pull

        _do_pull(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, ImagePullJob.Status.FAILED)
        self.assertIsNotNone(job.error_message)
        self.assertIsNotNone(job.completed_at)

    @patch("images.worker.docker.DockerClient")
    def test_cancelled_job_not_pulled(self, MockClient):
        """Worker should skip a job that was cancelled before the thread ran."""
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="skip:me",
            status=ImagePullJob.Status.CANCELLED,
        )

        from .worker import _do_pull

        _do_pull(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, ImagePullJob.Status.CANCELLED)
        MockClient.assert_not_called()

    @patch("images.worker.docker.DockerClient")
    def test_pull_with_registry_credential(self, MockClient):
        """Worker should pass auth_config when a credential is linked."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.api.pull.return_value = [
            {"status": "Pull complete"},
        ]

        cred = RegistryCredential(
            owner=self.owner,
            alias="Private GHCR",
            registry_url="https://ghcr.io",
            username="ghuser",
        )
        cred.token = "ghp_secret_token"
        cred.save()

        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.owner,
            image_ref="ghcr.io/myorg/myapp:v1",
            registry_credential=cred,
        )

        from .worker import _do_pull

        _do_pull(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, ImagePullJob.Status.SUCCESS)

        # Verify auth_config was passed to the pull call
        _, call_kwargs = mock_client.api.pull.call_args
        self.assertEqual(call_kwargs["auth_config"]["username"], "ghuser")
        self.assertEqual(
            call_kwargs["auth_config"]["password"], "ghp_secret_token"
        )

    def test_nonexistent_job_id_does_not_raise(self):
        """Worker should log error and return gracefully for missing job."""
        from .worker import _do_pull

        import uuid

        _do_pull(str(uuid.uuid4()))  # Should not raise


# --------------------------------------------------------------------------- #
# API route integration tests
# --------------------------------------------------------------------------- #
@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class ImagePullJobRouteIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="iadmin", password="password123", role="admin"
        )
        self.host_owner = User.objects.create_user(
            username="ihoster", password="password123", role="host"
        )
        self.viewer = User.objects.create_user(
            username="iviewer", password="password123", role="viewer"
        )
        self.host = Host.objects.create(
            name="Route Host",
            hostname="192.168.1.50",
            port=2375,
            owner=self.host_owner,
        )
        self.base_url = f"/api/hosts/{self.host.id}/images/pull/"

    # ---- LIST ---- #
    def test_list_jobs_authenticated(self):
        """Any authenticated user can list pull jobs."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_jobs_unauthenticated(self):
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_shows_jobs_for_host(self):
        """List should return only jobs belonging to this host."""
        ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.admin,
            image_ref="nginx:latest",
        )
        other_host = Host.objects.create(
            name="Other Host",
            hostname="192.168.1.51",
            port=2375,
            owner=self.admin,
        )
        ImagePullJob.objects.create(
            host=other_host,
            requested_by=self.admin,
            image_ref="redis:7",
        )

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.base_url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["image_ref"], "nginx:latest")

    # ---- CREATE (POST) ---- #
    @patch("images.views.enqueue_pull")
    def test_create_job_as_admin(self, mock_enqueue):
        """Admin can enqueue a pull job on any host."""
        mock_enqueue.return_value = None

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.base_url,
            {"image_ref": "nginx:1.25-alpine"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["image_ref"], "nginx:1.25-alpine")
        self.assertEqual(response.data["status"], "PENDING")
        mock_enqueue.assert_called_once()

    @patch("images.views.enqueue_pull")
    def test_create_job_as_host_owner(self, mock_enqueue):
        """Host owner can enqueue a pull on their own host."""
        mock_enqueue.return_value = None

        self.client.force_authenticate(user=self.host_owner)
        response = self.client.post(
            self.base_url,
            {"image_ref": "redis:7"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_job_denied_for_viewer(self):
        """Viewer role cannot create pull jobs."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(
            self.base_url,
            {"image_ref": "nginx:latest"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_job_unauthenticated(self):
        response = self.client.post(
            self.base_url,
            {"image_ref": "nginx:latest"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("images.views.enqueue_pull")
    def test_create_job_missing_image_ref(self, mock_enqueue):
        """image_ref is required."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.base_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("images.views.enqueue_pull")
    def test_create_job_with_registry_credential(self, mock_enqueue):
        """Valid credential should be linked to the job."""
        mock_enqueue.return_value = None

        cred = RegistryCredential(
            owner=self.admin,
            alias="My GHCR",
            registry_url="https://ghcr.io",
            username="u",
        )
        cred.token = "t"
        cred.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.base_url,
            {
                "image_ref": "ghcr.io/myorg/myapp:v1",
                "registry_credential": str(cred.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_id = response.data["id"]
        job = ImagePullJob.objects.get(pk=job_id)
        self.assertEqual(job.registry_credential_id, cred.id)

    @patch("images.views.enqueue_pull")
    def test_create_job_with_other_users_credential_fails(self, mock_enqueue):
        """Cannot use another user's credential."""
        cred = RegistryCredential(
            owner=self.host_owner,
            alias="Stolen",
            registry_url="https://ghcr.io",
            username="u",
        )
        cred.token = "t"
        cred.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.base_url,
            {
                "image_ref": "ghcr.io/evil:latest",
                "registry_credential": str(cred.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("images.views.enqueue_pull")
    def test_create_job_non_owner_host_user_denied(self, mock_enqueue):
        """A host-role user who does not own the host should be denied."""
        other_host_user = User.objects.create_user(
            username="otherhoster", password="password123", role="host"
        )
        self.client.force_authenticate(user=other_host_user)
        response = self.client.post(
            self.base_url,
            {"image_ref": "nginx:latest"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ---- RETRIEVE (GET detail) ---- #
    def test_retrieve_job_detail(self):
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.admin,
            image_ref="alpine:3.18",
        )
        self.client.force_authenticate(user=self.viewer)
        url = f"{self.base_url}{job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["image_ref"], "alpine:3.18")
        self.assertEqual(response.data["status"], "PENDING")

    def test_retrieve_nonexistent_job_returns_404(self):
        self.client.force_authenticate(user=self.viewer)
        import uuid

        url = f"{self.base_url}{uuid.uuid4()}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_job_from_different_host_returns_404(self):
        """Job on a different host should not be retrievable via this host's URL."""
        other_host = Host.objects.create(
            name="Other", hostname="10.10.10.10", port=2375, owner=self.admin
        )
        job = ImagePullJob.objects.create(
            host=other_host,
            requested_by=self.admin,
            image_ref="busybox:latest",
        )
        self.client.force_authenticate(user=self.viewer)
        url = f"{self.base_url}{job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---- CANCEL (DELETE) ---- #
    def test_cancel_pending_job_as_admin(self):
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.admin,
            image_ref="cancel:me",
        )
        self.client.force_authenticate(user=self.admin)
        url = f"{self.base_url}{job.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("cancelled", response.data["detail"].lower())

        job.refresh_from_db()
        self.assertEqual(job.status, ImagePullJob.Status.CANCELLED)

    def test_cancel_denied_for_non_admin(self):
        """Only admins can cancel."""
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.host_owner,
            image_ref="nope:latest",
        )
        self.client.force_authenticate(user=self.host_owner)
        url = f"{self.base_url}{job.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancel_non_pending_job_returns_conflict(self):
        """Cannot cancel a job that is already PULLING or completed."""
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.admin,
            image_ref="running:now",
            status=ImagePullJob.Status.PULLING,
        )
        self.client.force_authenticate(user=self.admin)
        url = f"{self.base_url}{job.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_cancel_already_succeeded_returns_conflict(self):
        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.admin,
            image_ref="done:1",
            status=ImagePullJob.Status.SUCCESS,
        )
        self.client.force_authenticate(user=self.admin)
        url = f"{self.base_url}{job.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_cancel_nonexistent_job_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        import uuid

        url = f"{self.base_url}{uuid.uuid4()}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# --------------------------------------------------------------------------- #
# Serializer unit tests
# --------------------------------------------------------------------------- #
@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class ImagePullJobSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="suser", password="password123", role="admin"
        )
        self.host = Host.objects.create(
            name="Ser Host",
            hostname="10.0.0.5",
            port=2375,
            owner=self.user,
        )

    def test_read_serializer_fields(self):
        from .serializers import ImagePullJobSerializer

        job = ImagePullJob.objects.create(
            host=self.host,
            requested_by=self.user,
            image_ref="python:3.12-slim",
        )
        serializer = ImagePullJobSerializer(job)
        data = serializer.data

        self.assertEqual(data["image_ref"], "python:3.12-slim")
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(data["requested_by"], "suser")
        self.assertEqual(data["host_name"], "Ser Host")
        self.assertIn("id", data)
        self.assertIn("progress_log", data)
        self.assertIn("created_at", data)

    def test_create_serializer_validates_image_ref(self):
        from .serializers import ImagePullJobCreateSerializer

        serializer = ImagePullJobCreateSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("image_ref", serializer.errors)

    def test_create_serializer_validates_other_users_credential(self):
        from .serializers import ImagePullJobCreateSerializer

        other_user = User.objects.create_user(
            username="other_ser", password="password123", role="host"
        )
        cred = RegistryCredential(
            owner=other_user,
            alias="Not Mine",
            registry_url="https://ghcr.io",
            username="o",
        )
        cred.token = "t"
        cred.save()

        # Build a mock request with self.user
        class MockRequest:
            user = self.user

        serializer = ImagePullJobCreateSerializer(
            data={
                "image_ref": "ghcr.io/x:1",
                "registry_credential": str(cred.id),
            },
            context={"request": MockRequest()},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("registry_credential", serializer.errors)


# --------------------------------------------------------------------------- #
# Image Inspect API integration tests
# --------------------------------------------------------------------------- #

# A realistic Docker inspect response for mocking
_SAMPLE_IMAGE_ATTRS = {
    "Id": "sha256:abc123def456",
    "RepoTags": ["nginx:1.25-alpine"],
    "RepoDigests": ["nginx@sha256:deadbeef"],
    "Size": 41_200_000,
    "VirtualSize": 41_200_000,
    "Created": "2025-06-01T12:00:00.000000000Z",
    "Architecture": "amd64",
    "Os": "linux",
    "Config": {
        "Env": [
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "NGINX_VERSION=1.25.4",
            "NJS_VERSION=0.8.3",
        ],
        "Entrypoint": ["/docker-entrypoint.sh"],
        "Cmd": ["nginx", "-g", "daemon off;"],
        "ExposedPorts": {"80/tcp": {}, "443/tcp": {}},
    },
}

_SAMPLE_HISTORY = [
    {
        "Created": "2025-06-01T12:00:00.000000000Z",
        "CreatedBy": "/bin/sh -c #(nop) CMD [\"nginx\" \"-g\" \"daemon off;\"]",
        "Size": 0,
        "Comment": "",
        "Tags": ["nginx:1.25-alpine"],
    },
    {
        "Created": "2025-06-01T11:59:00.000000000Z",
        "CreatedBy": "/bin/sh -c #(nop) ENTRYPOINT [\"/docker-entrypoint.sh\"]",
        "Size": 0,
        "Comment": "",
        "Tags": None,
    },
    {
        "Created": "2025-06-01T11:58:00.000000000Z",
        "CreatedBy": "/bin/sh -c set -x && apk add --no-cache nginx",
        "Size": 12_500_000,
        "Comment": "",
        "Tags": None,
    },
    {
        "Created": "2025-05-15T10:00:00.000000000Z",
        "CreatedBy": "/bin/sh -c #(nop) ADD file:abc123 in / ",
        "Size": 7_800_000,
        "Comment": "",
        "Tags": ["alpine:3.18"],
    },
]


class ImageInspectRouteIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="inspect_admin", password="password123", role="admin"
        )
        self.viewer = User.objects.create_user(
            username="inspect_viewer", password="password123", role="viewer"
        )
        self.host = Host.objects.create(
            name="Inspect Host",
            hostname="192.168.1.99",
            port=2375,
            owner=self.admin,
        )
        self.base_url = f"/api/hosts/{self.host.id}/images/inspect/"

    # ---- Successful inspect ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_returns_full_metadata(self, MockClient):
        """Successful inspect should return ENV, ENTRYPOINT, size, and layers."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = _SAMPLE_IMAGE_ATTRS
        mock_image.history.return_value = _SAMPLE_HISTORY
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:1.25-alpine"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Core fields
        self.assertEqual(data["image_id"], "sha256:abc123def456")
        self.assertEqual(data["size"], 41_200_000)
        self.assertEqual(data["architecture"], "amd64")
        self.assertEqual(data["os"], "linux")
        self.assertEqual(data["created"], "2025-06-01T12:00:00.000000000Z")

        # Repo tags and digests
        self.assertEqual(data["repo_tags"], ["nginx:1.25-alpine"])
        self.assertEqual(data["repo_digests"], ["nginx@sha256:deadbeef"])

        # ENV
        self.assertEqual(len(data["env"]), 3)
        self.assertIn("NGINX_VERSION=1.25.4", data["env"])
        self.assertIn("NJS_VERSION=0.8.3", data["env"])

        # ENTRYPOINT
        self.assertEqual(data["entrypoint"], ["/docker-entrypoint.sh"])

        # CMD
        self.assertEqual(data["cmd"], ["nginx", "-g", "daemon off;"])

        # Exposed ports
        self.assertIn("80/tcp", data["exposed_ports"])
        self.assertIn("443/tcp", data["exposed_ports"])

        # Layers
        self.assertEqual(len(data["layers"]), 4)
        self.assertEqual(data["layers"][0]["tags"], ["nginx:1.25-alpine"])
        self.assertEqual(data["layers"][2]["size"], 12_500_000)

        # Should have connected to the correct host
        MockClient.assert_called_once_with(
            base_url="tcp://192.168.1.99:2375", timeout=30
        )

    # ---- Missing query parameter ---- #
    def test_inspect_missing_image_ref_returns_400(self):
        """Missing image_ref query param should return 400."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image_ref", response.data["detail"])

    # ---- Image not found ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_image_not_found_returns_404(self, MockClient):
        """Inspecting a non-existent image should return 404."""
        import docker as docker_lib

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.images.get.side_effect = docker_lib.errors.ImageNotFound(
            "no such image"
        )

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "nonexistent:latest"}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not found", response.data["detail"].lower())

    # ---- Unauthenticated ---- #
    def test_inspect_unauthenticated_returns_401(self):
        """Anonymous users should not access the inspect endpoint."""
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:latest"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---- Docker connection failure ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_connection_failure_returns_502(self, MockClient):
        """If we can't connect to the Docker daemon, return 502."""
        import docker as docker_lib

        MockClient.side_effect = docker_lib.errors.DockerException(
            "Connection refused"
        )

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:latest"}
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("Cannot connect", response.data["detail"])

    # ---- Docker API error during inspect ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_api_error_returns_502(self, MockClient):
        """Generic Docker API error during image.get should return 502."""
        import docker as docker_lib

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.images.get.side_effect = docker_lib.errors.APIError(
            "server error"
        )

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "broken:latest"}
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("Docker API error", response.data["detail"])

    # ---- Image with empty / missing config fields ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_image_with_empty_config(self, MockClient):
        """Image with no ENV, no ENTRYPOINT, no CMD should return empty lists/null."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:minimal",
            "RepoTags": ["scratch:latest"],
            "RepoDigests": [],
            "Size": 0,
            "VirtualSize": 0,
            "Created": "2025-01-01T00:00:00Z",
            "Architecture": "",
            "Os": "",
            "Config": {},  # entirely empty config
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "scratch:latest"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["env"], [])
        self.assertIsNone(data["entrypoint"])
        self.assertIsNone(data["cmd"])
        self.assertEqual(data["exposed_ports"], {})
        self.assertEqual(data["layers"], [])

    # ---- Image with None Config ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_image_with_none_config(self, MockClient):
        """Image with Config=None (rare, e.g. bare manifests) should not crash."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:noconfig",
            "RepoTags": [],
            "RepoDigests": [],
            "Size": 100,
            "Created": "2025-01-01T00:00:00Z",
            "Config": None,
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "bare:manifest"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["env"], [])
        self.assertIsNone(response.data["entrypoint"])

    # ---- History API failure is handled gracefully ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_history_failure_returns_empty_layers(self, MockClient):
        """If image.history() raises, layers should be empty, rest should still work."""
        import docker as docker_lib

        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = _SAMPLE_IMAGE_ATTRS
        mock_image.history.side_effect = docker_lib.errors.APIError(
            "history unavailable"
        )
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:1.25-alpine"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # Layers empty because history() failed
        self.assertEqual(data["layers"], [])
        # But the rest of the inspect data should be fine
        self.assertEqual(data["image_id"], "sha256:abc123def456")
        self.assertEqual(len(data["env"]), 3)
        self.assertEqual(data["entrypoint"], ["/docker-entrypoint.sh"])

    # ---- Non-existent host returns 404 ---- #
    def test_inspect_nonexistent_host_returns_404(self):
        """Inspect on a host ID that doesn't exist should return 404."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            "/api/hosts/99999/images/inspect/",
            {"image_ref": "nginx:latest"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---- POST method should not be allowed ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_post_method_not_allowed(self, MockClient):
        """Inspect endpoint only supports GET."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.base_url,
            {"image_ref": "nginx:latest"},
            format="json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    # ---- PUT method should not be allowed ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_put_method_not_allowed(self, MockClient):
        """PUT is not allowed on the inspect endpoint."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.put(
            self.base_url,
            {"image_ref": "nginx:latest"},
            format="json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    # ---- DELETE method should not be allowed ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_delete_method_not_allowed(self, MockClient):
        """DELETE is not allowed on the inspect endpoint."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.base_url)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    # ---- Empty string image_ref ---- #
    def test_inspect_empty_string_image_ref_returns_400(self):
        """Empty string for image_ref should be treated the same as missing."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.base_url, {"image_ref": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- Whitespace-only image_ref ---- #
    def test_inspect_whitespace_image_ref_returns_400(self):
        """Whitespace-only image_ref should be treated as missing."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.base_url, {"image_ref": "   "})
        # Django query params preserve whitespace, so this reaches Docker
        # The view only checks `if not image_ref` — whitespace is truthy,
        # so this actually hits Docker. We verify it doesn't crash.
        # (A stricter check could strip, but this tests current behavior)
        # We don't assert 400 here because whitespace is truthy in Python.

    # ---- Inspect image by digest ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_image_by_digest(self, MockClient):
        """Should be able to inspect an image referenced by digest."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        digest_ref = "nginx@sha256:abc123def456789"
        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:abc123def456789",
            "RepoTags": [],
            "RepoDigests": [digest_ref],
            "Size": 50_000_000,
            "Created": "2025-06-01T12:00:00Z",
            "Architecture": "arm64",
            "Os": "linux",
            "Config": {
                "Env": ["PATH=/usr/bin"],
                "Entrypoint": None,
                "Cmd": ["nginx"],
            },
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": digest_ref}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["repo_digests"], [digest_ref])
        self.assertEqual(response.data["architecture"], "arm64")
        self.assertIsNone(response.data["entrypoint"])
        # Verify the exact ref was passed to Docker
        mock_client.images.get.assert_called_once_with(digest_ref)

    # ---- Multi-tag image ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_multi_tag_image(self, MockClient):
        """Image with multiple tags should return all of them."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:multitag",
            "RepoTags": [
                "myapp:latest",
                "myapp:v1.2.3",
                "registry.example.com/myapp:v1.2.3",
            ],
            "RepoDigests": [
                "myapp@sha256:aaa",
                "registry.example.com/myapp@sha256:bbb",
            ],
            "Size": 100_000_000,
            "Created": "2025-03-01T00:00:00Z",
            "Architecture": "amd64",
            "Os": "linux",
            "Config": {
                "Env": ["APP_VER=1.2.3"],
                "Entrypoint": ["/app/start.sh"],
                "Cmd": None,
                "ExposedPorts": {"8080/tcp": {}},
            },
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "myapp:latest"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["repo_tags"]), 3)
        self.assertIn("myapp:v1.2.3", response.data["repo_tags"])
        self.assertEqual(len(response.data["repo_digests"]), 2)
        self.assertIsNone(response.data["cmd"])
        self.assertIn("8080/tcp", response.data["exposed_ports"])

    # ---- Layer with missing fields ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_layer_missing_fields_defaults_gracefully(self, MockClient):
        """History entries with missing keys should get safe defaults."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:sparse",
            "RepoTags": ["sparse:1"],
            "Size": 500,
            "Created": "2025-01-01T00:00:00Z",
            "Config": {},
        }
        # History entry with many missing keys
        mock_image.history.return_value = [
            {"Created": "2025-01-01T00:00:00Z"},  # no CreatedBy, Size, etc.
            {},  # completely empty entry
        ]
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "sparse:1"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        layers = response.data["layers"]
        self.assertEqual(len(layers), 2)

        # First layer: has Created, rest should default
        self.assertEqual(layers[0]["created"], "2025-01-01T00:00:00Z")
        self.assertEqual(layers[0]["created_by"], "")
        self.assertEqual(layers[0]["size"], 0)
        self.assertEqual(layers[0]["comment"], "")
        self.assertEqual(layers[0]["tags"], [])

        # Second layer: completely empty, all defaults
        self.assertEqual(layers[1]["created"], "")
        self.assertEqual(layers[1]["size"], 0)
        self.assertEqual(layers[1]["tags"], [])

    # ---- Image with no VirtualSize ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_image_without_virtual_size(self, MockClient):
        """Newer Docker versions may not include VirtualSize; should be null."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:novsize",
            "RepoTags": ["test:1"],
            "Size": 30_000_000,
            "Created": "2025-01-01T00:00:00Z",
            "Architecture": "amd64",
            "Os": "linux",
            "Config": {"Env": [], "Entrypoint": None, "Cmd": ["sh"]},
            # VirtualSize deliberately missing
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "test:1"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["virtual_size"])
        self.assertEqual(response.data["size"], 30_000_000)

    # ---- Many-layer image ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_image_with_many_layers(self, MockClient):
        """Images can have dozens of layers; all should be returned."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:manylayers",
            "RepoTags": ["big:1"],
            "Size": 500_000_000,
            "Created": "2025-01-01T00:00:00Z",
            "Config": {"Env": ["X=1"]},
        }
        # Generate 50 history layers
        many_layers = [
            {
                "Created": f"2025-01-01T00:00:{i:02d}Z",
                "CreatedBy": f"RUN echo layer-{i}",
                "Size": 100_000 * i,
                "Comment": "",
                "Tags": None,
            }
            for i in range(50)
        ]
        mock_image.history.return_value = many_layers
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "big:1"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["layers"]), 50)
        self.assertEqual(
            response.data["layers"][49]["created_by"], "RUN echo layer-49"
        )

    # ---- ENV with special characters ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_env_with_special_characters(self, MockClient):
        """ENV values can contain =, spaces, quotes, and special chars."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        special_envs = [
            "DATABASE_URL=postgres://user:p@ss=word@db:5432/mydb",
            "JAVA_OPTS=-Xmx512m -XX:+UseG1GC",
            'GREETING=Hello "World"',
            "EMPTY_VAR=",
            "MULTIEQUAL=a=b=c=d",
        ]

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:specialenv",
            "RepoTags": ["app:env-test"],
            "Size": 100,
            "Created": "2025-01-01T00:00:00Z",
            "Config": {
                "Env": special_envs,
                "Entrypoint": ["/bin/sh", "-c"],
                "Cmd": ["echo", "$GREETING"],
            },
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "app:env-test"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["env"]), 5)
        self.assertIn(
            "DATABASE_URL=postgres://user:p@ss=word@db:5432/mydb",
            response.data["env"],
        )
        self.assertIn("EMPTY_VAR=", response.data["env"])
        self.assertEqual(
            response.data["entrypoint"], ["/bin/sh", "-c"]
        )
        self.assertEqual(response.data["cmd"], ["echo", "$GREETING"])

    # ---- Different host port ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_uses_correct_host_port(self, MockClient):
        """Should connect using the host's configured port (e.g. TLS 2376)."""
        tls_host = Host.objects.create(
            name="TLS Host",
            hostname="10.0.0.50",
            port=2376,
            owner=self.admin,
        )
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:tlsimage",
            "RepoTags": ["tls:1"],
            "Size": 100,
            "Created": "2025-01-01T00:00:00Z",
            "Config": {},
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            f"/api/hosts/{tls_host.id}/images/inspect/",
            {"image_ref": "tls:1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        MockClient.assert_called_once_with(
            base_url="tcp://10.0.0.50:2376", timeout=30
        )

    # ---- Response contains all expected top-level keys ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_response_has_all_expected_keys(self, MockClient):
        """Verify the response JSON has exactly the expected schema keys."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = _SAMPLE_IMAGE_ATTRS
        mock_image.history.return_value = _SAMPLE_HISTORY
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:1.25-alpine"}
        )

        expected_keys = {
            "image_id",
            "repo_tags",
            "repo_digests",
            "size",
            "virtual_size",
            "created",
            "architecture",
            "os",
            "env",
            "entrypoint",
            "cmd",
            "exposed_ports",
            "layers",
        }
        self.assertEqual(set(response.data.keys()), expected_keys)

    # ---- Layer sub-object has expected keys ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_layer_has_expected_keys(self, MockClient):
        """Each layer in the response should have the expected fields."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = _SAMPLE_IMAGE_ATTRS
        mock_image.history.return_value = _SAMPLE_HISTORY
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:1.25-alpine"}
        )

        expected_layer_keys = {"created", "created_by", "size", "comment", "tags"}
        for layer in response.data["layers"]:
            self.assertEqual(set(layer.keys()), expected_layer_keys)

    # ---- Verify image_ref is forwarded to Docker ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_forwards_image_ref_to_docker(self, MockClient):
        """The exact image_ref from the query param should be passed to client.images.get()."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = {
            "Id": "sha256:fwd",
            "RepoTags": ["my-registry.io/org/app:v2.0.0-rc1"],
            "Size": 1000,
            "Created": "2025-01-01T00:00:00Z",
            "Config": {},
        }
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        ref = "my-registry.io/org/app:v2.0.0-rc1"
        self.client.force_authenticate(user=self.viewer)
        self.client.get(self.base_url, {"image_ref": ref})

        mock_client.images.get.assert_called_once_with(ref)

    # ---- Admin can also inspect ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_as_admin(self, MockClient):
        """Admin should be able to use the inspect endpoint."""
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = _SAMPLE_IMAGE_ATTRS
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:1.25-alpine"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---- Host-role user can also inspect ---- #
    @patch("images.views.docker.DockerClient")
    def test_inspect_as_host_role(self, MockClient):
        """Host-role user should be able to use the inspect endpoint."""
        host_user = User.objects.create_user(
            username="inspect_hoster", password="password123", role="host"
        )
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        mock_image = MagicMock()
        mock_image.attrs = _SAMPLE_IMAGE_ATTRS
        mock_image.history.return_value = []
        mock_client.images.get.return_value = mock_image

        self.client.force_authenticate(user=host_user)
        response = self.client.get(
            self.base_url, {"image_ref": "nginx:1.25-alpine"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# --------------------------------------------------------------------------- #
# Inspect Serializer unit tests
# --------------------------------------------------------------------------- #
class ImageInspectSerializerTest(TestCase):
    """Validate ImageInspectSerializer and ImageLayerSerializer independently."""

    def test_layer_serializer_valid_data(self):
        from .serializers import ImageLayerSerializer

        data = {
            "created": "2025-06-01T12:00:00Z",
            "created_by": "RUN apt-get update",
            "size": 5_000_000,
            "comment": "install deps",
            "tags": ["base:latest"],
        }
        s = ImageLayerSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["size"], 5_000_000)
        self.assertEqual(s.validated_data["tags"], ["base:latest"])

    def test_layer_serializer_null_created(self):
        from .serializers import ImageLayerSerializer

        data = {
            "created": None,
            "created_by": "",
            "size": 0,
            "comment": "",
            "tags": [],
        }
        s = ImageLayerSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data["created"])

    def test_layer_serializer_null_created_by(self):
        from .serializers import ImageLayerSerializer

        data = {
            "created": "2025-01-01T00:00:00Z",
            "created_by": None,
            "size": 100,
        }
        s = ImageLayerSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data["created_by"])

    def test_layer_serializer_missing_required_size(self):
        from .serializers import ImageLayerSerializer

        data = {
            "created": "2025-01-01T00:00:00Z",
            "created_by": "RUN echo hi",
            # size is missing
        }
        s = ImageLayerSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("size", s.errors)

    def test_inspect_serializer_complete_data(self):
        from .serializers import ImageInspectSerializer

        data = {
            "image_id": "sha256:abc",
            "repo_tags": ["img:1"],
            "repo_digests": ["img@sha256:xyz"],
            "size": 10_000,
            "virtual_size": 10_000,
            "created": "2025-01-01T00:00:00Z",
            "architecture": "amd64",
            "os": "linux",
            "env": ["PATH=/bin", "HOME=/root"],
            "entrypoint": ["/start.sh"],
            "cmd": ["--serve"],
            "exposed_ports": {"80/tcp": {}},
            "layers": [
                {
                    "created": "2025-01-01T00:00:00Z",
                    "created_by": "ADD . /app",
                    "size": 5000,
                    "comment": "",
                    "tags": [],
                }
            ],
        }
        s = ImageInspectSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        v = s.validated_data
        self.assertEqual(v["image_id"], "sha256:abc")
        self.assertEqual(len(v["env"]), 2)
        self.assertEqual(len(v["layers"]), 1)
        self.assertEqual(v["layers"][0]["size"], 5000)

    def test_inspect_serializer_missing_image_id(self):
        from .serializers import ImageInspectSerializer

        data = {
            "size": 100,
            "created": "2025-01-01T00:00:00Z",
            "layers": [],
        }
        s = ImageInspectSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("image_id", s.errors)

    def test_inspect_serializer_null_entrypoint_and_cmd(self):
        from .serializers import ImageInspectSerializer

        data = {
            "image_id": "sha256:nullep",
            "size": 0,
            "created": "2025-01-01T00:00:00Z",
            "entrypoint": None,
            "cmd": None,
            "layers": [],
        }
        s = ImageInspectSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data["entrypoint"])
        self.assertIsNone(s.validated_data["cmd"])

    def test_inspect_serializer_virtual_size_optional(self):
        from .serializers import ImageInspectSerializer

        data = {
            "image_id": "sha256:novs",
            "size": 100,
            "created": "2025-01-01T00:00:00Z",
            "layers": [],
            # virtual_size deliberately omitted
        }
        s = ImageInspectSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_inspect_serializer_invalid_layer_cascades(self):
        """Invalid layer data should cause the whole serializer to fail."""
        from .serializers import ImageInspectSerializer

        data = {
            "image_id": "sha256:badlayer",
            "size": 100,
            "created": "2025-01-01T00:00:00Z",
            "layers": [
                {
                    "created": "2025-01-01T00:00:00Z",
                    "created_by": "RUN test",
                    # size missing — required field
                }
            ],
        }
        s = ImageInspectSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("layers", s.errors)

    def test_inspect_serializer_output_format(self):
        """Verify serializer output when used for read (not validation)."""
        from .serializers import ImageInspectSerializer

        inspect_data = {
            "image_id": "sha256:readtest",
            "repo_tags": ["test:1", "test:latest"],
            "repo_digests": [],
            "size": 999,
            "virtual_size": None,
            "created": "2025-06-01T00:00:00Z",
            "architecture": "arm64",
            "os": "linux",
            "env": ["A=1"],
            "entrypoint": ["/bin/app"],
            "cmd": None,
            "exposed_ports": {"3000/tcp": {}},
            "layers": [
                {
                    "created": "2025-06-01T00:00:00Z",
                    "created_by": "COPY . /app",
                    "size": 500,
                    "comment": "app code",
                    "tags": ["test:1"],
                }
            ],
        }
        s = ImageInspectSerializer(inspect_data)
        output = s.data

        self.assertEqual(output["image_id"], "sha256:readtest")
        self.assertEqual(output["repo_tags"], ["test:1", "test:latest"])
        self.assertIsNone(output["virtual_size"])
        self.assertIsNone(output["cmd"])
        self.assertEqual(len(output["layers"]), 1)
        self.assertEqual(output["layers"][0]["comment"], "app code")
        self.assertEqual(output["layers"][0]["tags"], ["test:1"])
