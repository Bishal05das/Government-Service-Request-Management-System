from django.db import models
from django.db.models.functions import Lower

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    """A type of government service (e.g. Water Supply, Road Maintenance)."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_category_name_ci"),
        ]

    def __str__(self):
        return self.name
