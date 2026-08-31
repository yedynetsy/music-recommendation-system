from django.db import models

from artists.models import Artist


class Album(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    release_date = models.DateField(null=True, blank=True)
    artist = models.ForeignKey(
        Artist,
        on_delete=models.PROTECT,
        related_name='albums'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.artist.name}"
