from rest_framework import serializers

from artists.serializers import ArtistSerializer
from .models import Album


class AlbumSerializer(serializers.ModelSerializer):
    artist_detail = ArtistSerializer(source='artist', read_only=True)

    class Meta:
        model = Album
        fields = [
            'id', 'name', 'description', 'release_date',
            'artist', 'artist_detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
