from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User
from apps.categories.models import Category

DEMO_USERS = [
    ("admin@gsr.local", Role.ADMIN, "System", "Admin"),
    ("officer@gsr.local", Role.OFFICER, "Olivia", "Officer"),
    ("citizen@gsr.local", Role.CITIZEN, "Carl", "Citizen"),
]

DEMO_CATEGORIES = [
    ("Water Supply", "Leaks, outages and water quality issues."),
    ("Road Maintenance", "Potholes, damaged roads and signage."),
    ("Waste Management", "Missed collections and illegal dumping."),
    ("Street Lighting", "Broken or missing street lights."),
    ("Birth & Death Certificates", "Issuance and correction of civil records."),
]


class Command(BaseCommand):
    help = "Create demo users (one per role) and service categories. Safe to run repeatedly."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="DemoPass123!", help="Password for all demo users.")

    @transaction.atomic
    def handle(self, *args, password, **options):
        for email, role, first_name, last_name in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"role": role, "first_name": first_name, "last_name": last_name, "is_email_verified": True,
                          "is_staff": role == Role.ADMIN, "is_superuser": role == Role.ADMIN},
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            self.stdout.write(f"{'created' if created else 'exists '}  {role:<8} {email}")

        for name, description in DEMO_CATEGORIES:
            _, created = Category.objects.get_or_create(name=name, defaults={"description": description})
            self.stdout.write(f"{'created' if created else 'exists '}  category {name}")

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
