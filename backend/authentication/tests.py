from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

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


class UserProfileTest(TestCase):
    """Test user profile endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.profile_url = '/api/auth/profile/'
        self.login_url = '/api/auth/login/'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='host',
            first_name='Test',
            last_name='User'
        )
    
    def test_get_profile_authenticated(self):
        # Login to get access token
        login_response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        access_token = login_response.data['access']
        
        # Get profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['role'], 'host')
        self.assertEqual(response.data['first_name'], 'Test')
        self.assertEqual(response.data['last_name'], 'User')
    
    def test_get_profile_unauthenticated(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_profile(self):
        # Login
        login_response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        access_token = login_response.data['access']
        
        # Update profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.patch(self.profile_url, {
            'first_name': 'Updated',
            'last_name': 'Name'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')
        self.assertEqual(response.data['last_name'], 'Name')
        
        # Verify in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')


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
