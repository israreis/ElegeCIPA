from django.conf import settings
from django.utils import timezone


def branding(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "ORGANIZATION_NAME": settings.ORGANIZATION_NAME,
        "current_year": timezone.localdate().year,
    }
