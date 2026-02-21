
from django.http import HttpResponse

from apps.bases.utils import get_file_contents


def terms(request):
    """
        Terms-and-conditions of the application
    """
    content = get_file_contents('resources/templates/terms.html')
    return HttpResponse(content)


def privacy(request):
    """
        Privacy-policy of the application
    """
    content = get_file_contents('resources/templates/privacy.html')
    return HttpResponse(content)


def about(request):
    """
        Introduction of the application
    """
    content = get_file_contents('resources/templates/about.html')
    return HttpResponse(content)


def partner_privacy(request):
    """Privacy Policy For Partners"""
    content = get_file_contents('resources/templates/partner_privacy_policy.html')
    return HttpResponse(content)


def partner_terms(request):
    """Terms and Conditions For Partners"""
    content = get_file_contents('resources/templates/partner_terms_and_conditions.html')
    return HttpResponse(content)
