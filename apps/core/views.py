import json
import re

import graphene
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from backend.authentication import Authentication
from .models import ValidArea


def _parse_areas_text(content):
    """Parse tab/space-separated text. Returns list of (post_code, name)."""
    seen = set()
    rows = []
    for line in (content or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[\t\s]+", line, maxsplit=1)
        if not parts:
            continue
        raw_code = parts[0].replace("\t", "").replace(" ", "")
        try:
            post_code = int(raw_code)
        except (ValueError, TypeError):
            continue
        if post_code < 0:
            continue
        if post_code in seen:
            continue
        seen.add(post_code)
        name = (parts[1].strip() if len(parts) > 1 else None) or None
        rows.append((post_code, name))
    return rows


@require_http_methods(["GET"])
def valid_areas_search(request):
    """
    GET ?term=z&first=100
    Returns JSON list of areas whose name contains term (icontains). Auth optional for read.
    """
    term = (request.GET.get("term") or "").strip()
    try:
        first = min(500, max(1, int(request.GET.get("first", 100))))
    except (TypeError, ValueError):
        first = 100
    qs = ValidArea.objects.all().order_by("name", "post_code")
    if term:
        qs = qs.filter(name__icontains=term)
    # Use relay global ID so vendor can pass these to setVendorServiceAreas mutation
    areas = []
    for a in qs[:first]:
        gid = graphene.relay.Node.to_global_id("ValidAreaType", a.id)
        areas.append({"id": gid, "name": a.name, "postCode": a.post_code, "isActive": a.is_active})
    return JsonResponse({"data": areas})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(require_http_methods(["POST"]), name="dispatch")
class ImportAreasView(View):
    """
    POST body = raw text (one line per row, tab/space separated: post_code, name).
    Requires Authorization: JWT <token> and admin user.
    """

    def post(self, request):
        user = Authentication(request).authenticate()
        if not user:
            return JsonResponse(
                {"success": False, "message": "Unauthorized"},
                status=401,
            )
        if not user.is_admin:
            return JsonResponse(
                {"success": False, "message": "Forbidden"},
                status=403,
            )
        try:
            body = request.body
            if not body:
                return JsonResponse(
                    {"success": False, "message": "Empty body"},
                    status=400,
                )
            content = body.decode("utf-8")
        except UnicodeDecodeError:
            return JsonResponse(
                {"success": False, "message": "Invalid encoding (use UTF-8)"},
                status=400,
            )
        rows = _parse_areas_text(content)
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        for post_code, name in rows:
            try:
                obj, created = ValidArea.objects.update_or_create(
                    post_code=post_code,
                    defaults={"name": name, "is_active": True},
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"Post code {post_code}: {str(e)}")
        return JsonResponse(
            {
                "success": True,
                "message": f"Import complete: {created_count} created, {updated_count} updated, {error_count} errors.",
                "created_count": created_count,
                "updated_count": updated_count,
                "error_count": error_count,
                "errors": errors[:50] if errors else None,
            },
        )
