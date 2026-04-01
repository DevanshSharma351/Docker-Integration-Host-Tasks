from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Host, UserHostRole

User = get_user_model()

class HostTests(APITestCase):
    def setUp(self):
        # 1. Create Users
        self.admin = User.objects.create_user(username='admin', password='pass123', is_staff=True)
        self.viewer = User.objects.create_user(username='viewer', password='pass123')
        self.other_user = User.objects.create_user(username='other', password='pass123')

        # 2. Create a Host (as Admin)
        self.host = Host.objects.create(
            alias='Production Server',
            ip_address='192.168.1.10',
            port=2375,
            ssh_credentials='encrypted_key',
            created_by=self.admin
        )

        # 3. Assign viewer to the host
        UserHostRole.objects.create(
            user=self.viewer,
            host=self.host,
            role='VIEWER',
            assigned_by=self.admin
        )

        self.list_url = reverse('host-list-create') 
        self.detail_url = reverse('host-detail', kwargs={'id': self.host.id})
        self.assign_url = reverse('host-assign', kwargs={'id': self.host.id})

    # --- HOST MANAGEMENT TESTS ---

    def test_admin_can_create_host(self):
        self.client.force_authenticate(user=self.admin)
        data = {
            'alias': 'Staging',
            'ip_address': '10.0.0.5',
            'port': 2376,
            'ssh_credentials': 'new_secret'
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Host.objects.count(), 2)

    def test_viewer_cannot_create_host(self):
        self.client.force_authenticate(user=self.viewer)
        data = {'alias': 'Hack', 'ip_address': '1.1.1.1', 'port': 80}
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_host_list_filtering_by_role(self):
        """Test that users only see hosts they are assigned to."""
        # Create a second host that viewer is NOT assigned to
        Host.objects.create(alias='Private Host', ip_address='0.0.0.0', port=22, created_by=self.admin)
        
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.list_url)
        
        # Viewer should only see 1 host (the one assigned in setUp)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['alias'], 'Production Server')

    # --- ROLE ASSIGNMENT TESTS ---

    def test_admin_can_assign_role(self):
        self.client.force_authenticate(user=self.admin)
        data = {
            'user_id': str(self.other_user.id),
            'role': 'HOST_OWNER'
        }
        response = self.client.post(self.assign_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserHostRole.objects.filter(user=self.other_user, host=self.host).exists())

    def test_non_admin_cannot_assign_role(self):
        self.client.force_authenticate(user=self.viewer)
        data = {'user_id': str(self.other_user.id), 'role': 'ADMIN'}
        response = self.client.post(self.assign_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_remove_user_access(self):
        self.client.force_authenticate(user=self.admin)
        # DELETE /api/hosts/{id}/assign/{user_id}/
        url = reverse('host-remove-user', kwargs={'id': self.host.id, 'user_id': self.viewer.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserHostRole.objects.filter(user=self.viewer, host=self.host).exists())

    # --- SECURITY TESTS ---

    def test_unassigned_user_cannot_view_host_detail(self):
        """other_user is logged in but not assigned to host."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ssh_credentials_not_in_response(self):
        """Ensure sensitive data is never leaked in GET requests."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.detail_url)
        self.assertNotIn('ssh_credentials', response.data)