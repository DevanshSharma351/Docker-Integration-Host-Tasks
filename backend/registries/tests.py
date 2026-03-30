from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from .encryption import decrypt_token, encrypt_token
from .models import RegistryCredential
from .permissions import IsCredentialOwner

User = get_user_model()

# A valid Fernet key for tests (generated via Fernet.generate_key()).
TEST_ENCRYPTION_KEY = "ZXcxMjNkRmVybmV0S2V5X18xMjM0NTY3ODkwYWJjZD0="


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class EncryptionUnitTest(TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        plain = "my-secret-token-123!"
        encrypted = encrypt_token(plain)
        self.assertNotEqual(encrypted, plain)
        self.assertEqual(decrypt_token(encrypted), plain)

    def test_different_plaintexts_produce_different_ciphertexts(self):
        a = encrypt_token("alpha")
        b = encrypt_token("bravo")
        self.assertNotEqual(a, b)


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class RegistryCredentialModelUnitTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="regowner", password="password123")

    def test_string_representation(self):
        cred = RegistryCredential(
            owner=self.owner,
            alias="My DockerHub",
            registry_url="https://index.docker.io/v1/",
            username="dockeruser",
        )
        cred.token = "secret"
        cred.save()
        self.assertEqual(str(cred), "My DockerHub (https://index.docker.io/v1/)")

    def test_token_encryption_on_save(self):
        cred = RegistryCredential(
            owner=self.owner,
            alias="GHCR",
            registry_url="https://ghcr.io",
            username="ghuser",
        )
        cred.token = "ghp_supersecret"
        cred.save()

        # Read from DB directly – internal field must be encrypted
        from_db = RegistryCredential.objects.get(pk=cred.pk)
        self.assertNotEqual(from_db._encrypted_token, "ghp_supersecret")
        self.assertEqual(from_db.token, "ghp_supersecret")


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class RegistryCredentialPermissionUnitTest(TestCase):
    def setUp(self):
        self.permission = IsCredentialOwner()
        self.owner = User.objects.create_user(username="powner", password="password123")
        self.other = User.objects.create_user(username="other", password="password123")
        self.cred = RegistryCredential(
            owner=self.owner,
            alias="test",
            registry_url="https://index.docker.io/v1/",
            username="u",
        )
        self.cred.token = "t"
        self.cred.save()

    def _request(self, method, user):
        class DummyRequest:
            pass
        r = DummyRequest()
        r.method = method
        r.user = user
        return r

    def test_read_allowed_for_non_owner(self):
        req = self._request("GET", self.other)
        self.assertTrue(self.permission.has_object_permission(req, None, self.cred))

    def test_write_denied_for_non_owner(self):
        req = self._request("PUT", self.other)
        self.assertFalse(self.permission.has_object_permission(req, None, self.cred))

    def test_delete_allowed_for_owner(self):
        req = self._request("DELETE", self.owner)
        self.assertTrue(self.permission.has_object_permission(req, None, self.cred))


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class RegistryCredentialRouteIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password123", role="admin")
        self.other = User.objects.create_user(username="otheruser", password="password123", role="admin")
        self.client.force_authenticate(user=self.user)

        # Pre-create a credential for detail / update / delete tests
        self.cred = RegistryCredential(
            owner=self.user,
            alias="CI Registry",
            registry_url="https://index.docker.io/v1/",
            username="ciuser",
        )
        self.cred.token = "citoken123"
        self.cred.save()
        self.base_url = "/api/registries/"
        self.detail_url = f"{self.base_url}{self.cred.id}/"

    # ---- LIST ---- #
    def test_list_returns_own_credentials(self):
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertNotIn("token", response.data[0])

    def test_list_does_not_return_other_users_credentials(self):
        other_cred = RegistryCredential(
            owner=self.other,
            alias="Other Reg",
            registry_url="https://ghcr.io",
            username="ou",
        )
        other_cred.token = "x"
        other_cred.save()

        response = self.client.get(self.base_url)
        aliases = [c["alias"] for c in response.data]
        self.assertNotIn("Other Reg", aliases)

    # ---- CREATE ---- #
    def test_create_credential(self):
        response = self.client.post(
            self.base_url,
            {
                "alias": "New Reg",
                "registry_url": "https://ghcr.io",
                "username": "newuser",
                "token": "newtoken",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RegistryCredential.objects.filter(alias="New Reg").exists())
        # Token must NOT appear in response
        self.assertNotIn("token", response.data)

    def test_create_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            self.base_url,
            {
                "alias": "Anon",
                "registry_url": "https://x.io",
                "username": "u",
                "token": "t",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---- RETRIEVE ---- #
    def test_retrieve_credential(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["alias"], "CI Registry")

    # ---- UPDATE ---- #
    def test_update_credential_by_owner(self):
        response = self.client.put(
            self.detail_url,
            {
                "alias": "Updated Alias",
                "registry_url": "https://index.docker.io/v1/",
                "username": "ciuser",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cred.refresh_from_db()
        self.assertEqual(self.cred.alias, "Updated Alias")

    def test_update_denied_for_non_owner(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.put(
            self.detail_url,
            {"alias": "Hacked"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---- DELETE ---- #
    def test_delete_credential_by_owner(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RegistryCredential.objects.filter(pk=self.cred.pk).exists())

    def test_delete_denied_for_non_owner(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---- VERIFY ---- #
    @patch("registries.views.docker")
    def test_verify_success(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.login.return_value = {"Status": "Login Succeeded"}

        verify_url = f"{self.detail_url}verify/"
        response = self.client.post(verify_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Login successful", response.data["detail"])

        mock_client.login.assert_called_once_with(
            username="ciuser",
            password="citoken123",
            registry="https://index.docker.io/v1/",
        )

        self.cred.refresh_from_db()
        self.assertIsNotNone(self.cred.last_verified_at)

    @patch("registries.views.docker")
    def test_verify_failure(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors.APIError = Exception
        mock_client.login.side_effect = Exception("unauthorized")

        verify_url = f"{self.detail_url}verify/"
        response = self.client.post(verify_url)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR])
