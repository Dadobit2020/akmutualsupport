from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.identity.urls")),
    path("api/v1/members/", include("apps.membership.urls")),
    path("api/v1/events/", include("apps.events.urls")),
    path("api/v1/ledger/", include("apps.ledger.urls")),
    path("api/v1/obligations/", include("apps.obligations.urls")),
    path("api/v1/reconciliation/", include("apps.reconciliation.urls")),
    path("api/v1/communications/", include("apps.communications.urls")),
    path("api/v1/reports/", include("apps.reporting.urls")),
    path("api/v1/me/", include("apps.portal.urls")),
    path("api/v1/exports/", include("apps.reporting.export_urls")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
