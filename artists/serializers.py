from rest_framework import serializers

from .models import Artist


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = ['id', 'name', 'bio', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
