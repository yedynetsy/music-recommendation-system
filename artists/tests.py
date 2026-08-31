import pytest

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .models import Artist

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user():
    return User.objects.create_user(username="admin", password="pass123", is_staff=True)

@pytest.fixture
def regular_user():
    return User.objects.create_user(username="user", password="pass123")

@pytest.fixture
def artist():
    return Artist.objects.create(name="Nirvana", bio="Rock band")


@pytest.mark.django_db
def test_create_artist_success(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/artists/', {'name': 'Radiohead'})
    assert response.status_code == 201
    assert response.data['name'] == 'Radiohead'

@pytest.mark.django_db
def test_update_artist(api_client, admin_user, artist):
    api_client.force_authenticate(user=admin_user)
    response = api_client.put(f'/api/artists/{artist.id}/', {'name': 'Nirvana Updated'})
    assert response.status_code == 200
    assert response.data['name'] == 'Nirvana Updated'

@pytest.mark.django_db
def test_delete_artist(api_client, admin_user, artist):
    api_client.force_authenticate(user=admin_user)
    response = api_client.delete(f'/api/artists/{artist.id}/')
    assert response.status_code == 204
    assert Artist.objects.count() == 0

@pytest.mark.django_db
def test_retrieve_artist(api_client, artist):
    response = api_client.get(f'/api/artists/{artist.id}/')
    assert response.status_code == 200
    assert response.data['name'] == 'Nirvana'

@pytest.mark.django_db
def test_list_artists(api_client, artist):
    response = api_client.get('/api/artists/')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['name'] == 'Nirvana'


@pytest.mark.django_db
def test_create_artist_unauthenticated(api_client):
    response = api_client.post('/api/artists/', {'name': 'Radiohead'})
    assert response.status_code == 401

@pytest.mark.django_db
def test_create_artist_non_admin(api_client, regular_user):
    api_client.force_authenticate(user=regular_user)
    response = api_client.post('/api/artists/', {'name': 'Radiohead'})
    assert response.status_code == 403

@pytest.mark.django_db
def test_delete_artist_non_admin(api_client, regular_user, artist):
    api_client.force_authenticate(user=regular_user)
    response = api_client.delete(f'/api/artists/{artist.id}/')
    assert response.status_code == 403

@pytest.mark.django_db
def test_create_artist_missing_name(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/artists/', {})
    assert response.status_code == 400
    assert 'name' in response.data

@pytest.mark.django_db
def test_retrieve_nonexistent_artist(api_client):
    response = api_client.get('/api/artists/999/')
    assert response.status_code == 404
