from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from hosts.models import Host

User = get_user_model()


class UserModelTest(TestCase):
    """Test custom User model"""
    
    def test_create_user_with_role(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='viewer'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.role, 'viewer')
        self.assertTrue(user.check_password('testpass123'))
    
    def test_default_role_is_viewer(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.assertEqual(user.role, 'viewer')
    
    def test_user_string_representation(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='admin'
        )
        self.assertEqual(str(user), 'testuser (admin)')


class RegistrationTest(TestCase):
    """Test user registration endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/auth/register/'
    
    def test_register_user_success(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'role': 'host',
            'first_name': 'New',
            'last_name': 'User'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'newuser')
        self.assertEqual(User.objects.get().role, 'host')
    
    def test_register_user_default_role(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get().role, 'viewer')
    
    def test_register_user_missing_username(self):
        data = {
            'email': 'new@example.com',
            'password': 'newpass123'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_user_short_password(self):
        data = {
            'username': 'newuser',
            'password': 'short'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_duplicate_username(self):
        User.objects.create_user(username='existing', password='pass123')
        data = {
            'username': 'existing',
            'password': 'newpass123'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_host_creates_default_host_record(self):
        data = {
            'username': 'hostregister',
            'password': 'newpass123',
            'role': 'host',
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='hostregister')
        host = Host.objects.filter(owner=user).first()
        self.assertIsNotNone(host)
        self.assertEqual(host.hostname, 'localhost')
        self.assertEqual(host.port, 2375)

    def test_register_viewer_does_not_create_host_record(self):
        data = {
            'username': 'viewerregister',
            'password': 'newpass123',
            'role': 'viewer',
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='viewerregister')
        self.assertFalse(Host.objects.filter(owner=user).exists())


class LoginTest(TestCase):
    """Test JWT login endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.login_url = '/api/auth/login/'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='admin'
        )
    
    def test_login_success(self):
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['role'], 'admin')
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
    
    def test_login_wrong_password(self):
        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_nonexistent_user(self):
        data = {
            'username': 'nonexistent',
            'password': 'testpass123'
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_missing_credentials(self):
        response = self.client.post(self.login_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_host_creates_default_host_if_missing(self):
        host_user = User.objects.create_user(
            username='hostlogin',
            password='hostpass123',
            role='host',
        )
        self.assertFalse(Host.objects.filter(owner=host_user).exists())

        response = self.client.post(self.login_url, {
            'username': 'hostlogin',
            'password': 'hostpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Host.objects.filter(owner=host_user).exists())

    def test_login_host_does_not_duplicate_default_host(self):
        host_user = User.objects.create_user(
            username='hostnodup',
            password='hostpass123',
            role='host',
        )
        Host.objects.create(
            name='existing',
            hostname='localhost',
            port=2375,
            owner=host_user,
        )

        response = self.client.post(self.login_url, {
            'username': 'hostnodup',
            'password': 'hostpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Host.objects.filter(owner=host_user).count(), 1)


class TokenRefreshTest(TestCase):
    """Test JWT token refresh endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.login_url = '/api/auth/login/'
        self.refresh_url = '/api/auth/token/refresh/'
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_refresh_token_success(self):
        # Login to get tokens
        login_response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        refresh_token = login_response.data['refresh']
        
        # Refresh the token
        response = self.client.post(self.refresh_url, {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_refresh_token_invalid(self):
        response = self.client.post(self.refresh_url, {
            'refresh': 'invalid_token'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PermissionsTest(TestCase):
    """Test role-based permissions"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin',
            password='pass123',
            role='admin'
        )
        self.host_user = User.objects.create_user(
            username='host',
            password='pass123',
            role='host'
        )
        self.viewer_user = User.objects.create_user(
            username='viewer',
            password='pass123',
            role='viewer'
        )
    
    def test_admin_role_assignment(self):
        self.assertEqual(self.admin_user.role, 'admin')
    
    def test_host_role_assignment(self):
        self.assertEqual(self.host_user.role, 'host')
    
    def test_viewer_role_assignment(self):
        self.assertEqual(self.viewer_user.role, 'viewer')
