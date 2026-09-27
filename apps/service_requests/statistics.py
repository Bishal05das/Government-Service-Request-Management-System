from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.categories.models import Category

from .models import Priority, ServiceRequest, Status

OPEN_STATUSES = [Status.SUBMITTED, Status.ASSIGNED, Status.IN_PROGRESS]


def _counts_by(queryset, field, choices):
    """Count rows per choice value, including zero counts for unused values."""
    rows = dict(queryset.values_list(field).annotate(n=Count("id")))
    return {value: rows.get(value, 0) for value, _ in choices}


def build_statistics():
    now = timezone.now()
    requests = ServiceRequest.objects.all()

    resolution_time = (
        requests.filter(resolved_at__isnull=False)
        .annotate(duration=ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField()))
        .aggregate(avg=Avg("duration"))["avg"]
    )

    by_category = (
        Category.objects.annotate(
            total=Count("service_requests"),
            open=Count("service_requests", filter=Q(service_requests__status__in=OPEN_STATUSES)),
        )
        .order_by("-total", "name")
        .values("id", "name", "total", "open")
    )

    officers = (
        User.objects.filter(role=Role.OFFICER)
        .annotate(
            open=Count("assigned_requests", filter=Q(assigned_requests__status__in=OPEN_STATUSES)),
            resolved=Count(
                "assigned_requests",
                filter=Q(assigned_requests__status__in=[Status.RESOLVED, Status.CLOSED]),
            ),
        )
        .order_by("-open", "email")
        .values("id", "email", "is_active", "open", "resolved")
    )

    return {
        "requests": {
            "total": requests.count(),
            "open": requests.filter(status__in=OPEN_STATUSES).count(),
            "unassigned": requests.filter(status=Status.SUBMITTED).count(),
            "created_last_7_days": requests.filter(created_at__gte=now - timedelta(days=7)).count(),
            "created_last_30_days": requests.filter(created_at__gte=now - timedelta(days=30)).count(),
            "by_status": _counts_by(requests, "status", Status.choices),
            "by_priority": _counts_by(requests, "priority", Priority.choices),
            "average_resolution_hours": (
                round(resolution_time.total_seconds() / 3600, 2) if resolution_time else None
            ),
        },
        "by_category": list(by_category),
        "officer_workload": list(officers),
        "users_by_role": _counts_by(User.objects.all(), "role", Role.choices),
    }
