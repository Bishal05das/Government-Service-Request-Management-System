from .models import AuditLog


def client_ip(request):
    # REMOTE_ADDR only: X-Forwarded-For is client-controlled unless a trusted proxy rewrites it.
    return request.META.get("REMOTE_ADDR") if request is not None else None


def record(action, *, request=None, actor=None, target=None, changes=None):
    """
    Write an audit entry. The actor defaults to the authenticated user on the request.
    `target` is any model instance; its model name and pk are stored.
    """
    if actor is None and request is not None and request.user.is_authenticated:
        actor = request.user
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.model_name if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        changes=changes or {},
        ip_address=client_ip(request),
    )


def diff(instance, new_values, exclude=("password",)):
    """{field: {"from": old, "to": new}} for fields whose value actually changes."""
    changes = {}
    for field, new in new_values.items():
        if field in exclude:
            if new:
                changes[field] = "changed"
            continue
        old = getattr(instance, field, None)
        old_cmp = getattr(old, "pk", old)
        new_cmp = getattr(new, "pk", new)
        if old_cmp != new_cmp:
            changes[field] = {"from": old_cmp, "to": new_cmp}
    return changes
