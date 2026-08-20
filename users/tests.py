import pytest
from rest_framework.test import APIClient
from .models import User


@pytest.mark.django_db
def test_register_success():
    client = APIClient()
    data = {
        "username": "testuser",
        "password": "testpassword",
        "password_confirm": "testpassword"
    }
    response = client.post("/api/user/register/", data=data)
    assert response.status_code == 201
    assert 'token' in response.data
    assert response.data['username'] == "testuser"

@pytest.mark.django_db
def test_register_duplicate_username():
    User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    data = {
        "username": "testuser",
        "password": "testpassword",
        "password_confirm": "testpassword"
    }
    response = client.post("/api/user/register/", data=data)
    assert response.status_code == 400
    assert 'username' in response.data

@pytest.mark.django_db
def test_register_password_mismatch():
    client = APIClient()
    data = {
        "username": "testuser",
        "password": "testpassword",
        "password_confirm": "differentpassword"
    }
    response = client.post("/api/user/register/", data=data)
    assert response.status_code == 400
    assert 'non_field_errors' in response.data

@pytest.mark.django_db
def test_login_success():
    user = User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    data = {
        "username": "testuser",
        "password": "testpassword"
    }
    response = client.post("/api/user/login/", data=data)
    assert response.status_code == 200
    assert 'token' in response.data
    assert response.data['username'] == "testuser"

@pytest.mark.django_db
def test_login_invalid_username():
    User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    data = {
        "username": "nonexistentuser",
        "password": "testpassword"
    }
    response = client.post("/api/user/login/", data=data)
    assert response.status_code == 400
    assert 'non_field_errors' in response.data

@pytest.mark.django_db
def test_login_invalid_password():
    user = User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    data = {
        "username": "testuser",
        "password": "wrongpassword"
    }
    response = client.post("/api/user/login/", data=data)
    assert response.status_code == 400
    assert 'non_field_errors' in response.data
