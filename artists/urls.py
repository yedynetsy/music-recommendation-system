from django.urls import path

from .views import (
    ArtistListCreateView,
    ArtistDetailView,
)


urlpatterns = [
    path('', ArtistListCreateView.as_view(), name='artist-list-create'),
    path('<int:pk>/', ArtistDetailView.as_view(), name='artist-detail'),
]
