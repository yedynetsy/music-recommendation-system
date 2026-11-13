import pytest

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from artists.models import Artist
from .models import Album

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

@pytest.fixture
def album(artist):
    return Album.objects.create(
        name="Nevermind",
        description="Second studio album",
        release_date="1991-09-24",
        artist=artist
    )


@pytest.mark.django_db
def test_create_album_success(api_client, admin_user, artist):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/albums/', {
        'name': 'In Utero',
        'description': 'Third studio album',
        'release_date': '1993-09-13',
        'artist': artist.id,
    })
    assert response.status_code == 201
    assert response.data['name'] == 'In Utero'
    assert Album.objects.count() == 1
    assert Album.objects.filter(name='In Utero').exists()

@pytest.mark.django_db
def test_retrieve_album(api_client, album):
    response = api_client.get(f'/api/albums/{album.id}/')
    assert response.status_code == 200
    assert response.data['name'] == 'Nevermind'

@pytest.mark.django_db
def test_update_album(api_client, admin_user, album):
    api_client.force_authenticate(user=admin_user)
    response = api_client.patch(f'/api/albums/{album.id}/', {'name': 'Nevermind Remastered'})
    assert response.status_code == 200
    assert response.data['name'] == 'Nevermind Remastered'

@pytest.mark.django_db
def test_delete_album(api_client, admin_user, album):
    api_client.force_authenticate(user=admin_user)
    response = api_client.delete(f'/api/albums/{album.id}/')
    assert response.status_code == 204
    assert Album.objects.count() == 0

@pytest.mark.django_db
def test_list_albums_ordering(api_client, artist):
    Album.objects.create(name="Zzz Album", artist=artist)
    Album.objects.create(name="Aaa Album", artist=artist)

    response = api_client.get('/api/albums/')
    assert response.status_code == 200
    names = [item['name'] for item in response.data]
    assert names == sorted(names)


@pytest.mark.django_db
def test_create_album_unauthenticated(api_client, artist):
    response = api_client.post('/api/albums/', {'name': 'Ghost Album', 'artist': artist.id})
    assert response.status_code == 401

@pytest.mark.django_db
def test_create_album_non_admin(api_client, regular_user, artist):
    api_client.force_authenticate(user=regular_user)
    response = api_client.post('/api/albums/', {'name': 'Ghost Album', 'artist': artist.id})
    assert response.status_code == 403

@pytest.mark.django_db
def test_delete_album_non_admin(api_client, regular_user, album):
    api_client.force_authenticate(user=regular_user)
    response = api_client.delete(f'/api/albums/{album.id}/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_create_album_missing_name(api_client, admin_user, artist):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/albums/', {'artist': artist.id})
    assert response.status_code == 400
    assert 'name' in response.data

@pytest.mark.django_db
def test_create_album_missing_artist(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/albums/', {'name': 'No Artist Album'})
    assert response.status_code == 400
    assert 'artist' in response.data

@pytest.mark.django_db
def test_create_album_nonexistent_artist(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/albums/', {'name': 'Ghost Album', 'artist': 999})
    assert response.status_code == 400
    assert 'artist' in response.data

@pytest.mark.django_db
def test_retrieve_nonexistent_album(api_client):
    response = api_client.get('/api/albums/999/')
    assert response.status_code == 404

@pytest.mark.django_db
def test_create_album_without_release_date(api_client, admin_user, artist):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post('/api/albums/', {'name': 'Undated Album', 'artist': artist.id})
    assert response.status_code == 201
    assert response.data['release_date'] is None


@pytest.mark.django_db
def test_album_response_includes_artist_detail(api_client, album, artist):
    response = api_client.get(f'/api/albums/{album.id}/')
    assert response.status_code == 200
    assert response.data['artist_detail']['id'] == artist.id
    assert response.data['artist_detail']['name'] == artist.name

@pytest.mark.django_db
def test_delete_artist_with_albums_fails(album, artist):
    with pytest.raises(ProtectedError):
        artist.delete()
    assert Artist.objects.filter(id=artist.id).exists()
