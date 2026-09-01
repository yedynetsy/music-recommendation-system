from rest_framework import generics
from rest_framework.permissions import IsAdminUser, AllowAny

from .models import Album
from .serializers import AlbumSerializer


class AlbumListCreateView(generics.ListCreateAPIView):
    queryset = Album.objects.select_related('artist')
    serializer_class = AlbumSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]


class AlbumDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Album.objects.select_related('artist')
    serializer_class = AlbumSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]
