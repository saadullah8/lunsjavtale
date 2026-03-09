"""
Create a supplier (vendor + owner user) in the database.

Usage:
  python manage.py add_supplier --name "My Supplier" --email supplier@example.com --password secret123
  python manage.py add_supplier --name "Acme" --email acme@test.com --password pass --contact "+4712345678" --post-code 1234
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.choices import RoleTypeChoices
from apps.users.models import User, Vendor


class Command(BaseCommand):
    help = "Add a supplier (vendor) and its owner user to the database."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Vendor/supplier name (unique)")
        parser.add_argument("--email", required=True, help="Owner email (used for login)")
        parser.add_argument("--password", required=True, help="Owner password")
        parser.add_argument(
            "--contact",
            default="",
            help="Phone number (e.g. +4712345678)",
        )
        parser.add_argument(
            "--post-code",
            type=int,
            default=None,
            help="Post code (optional)",
        )
        parser.add_argument(
            "--no-verify",
            action="store_true",
            help="Skip marking email as verified (default: mark verified so they can log in)",
        )

    def handle(self, *args, **options):
        name = options["name"].strip()
        email = options["email"].strip().lower()
        password = options["password"]
        contact = (options["contact"] or "").strip() or None
        post_code = options["post_code"]
        mark_verified = not options["no_verify"]

        if not name:
            self.stderr.write(self.style.ERROR("--name cannot be empty"))
            return
        if not email:
            self.stderr.write(self.style.ERROR("--email cannot be empty"))
            return
        if not password:
            self.stderr.write(self.style.ERROR("--password cannot be empty"))
            return

        if Vendor.objects.filter(name=name).exists():
            self.stderr.write(self.style.ERROR(f"Vendor with name '{name}' already exists."))
            return
        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f"User with email '{email}' already exists."))
            return

        with transaction.atomic():
            vendor = Vendor.objects.create(
                name=name,
                email=email,
                contact=contact,
                post_code=post_code,
            )
            user = User.objects.create_user(
                email=email,
                password=password,
                phone=contact,
                role=RoleTypeChoices.VENDOR,
                first_name=name.split()[0] if name else name,
                vendor=vendor,
            )
            if mark_verified:
                user.is_verified = True
                user.is_email_verified = True
                user.save(update_fields=["is_verified", "is_email_verified"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Supplier created: vendor id={vendor.id}, user id={user.id}, email={email}"
            )
        )
