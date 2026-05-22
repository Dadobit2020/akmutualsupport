from rest_framework.routers import DefaultRouter
from .views import ObligationViewSet, PaymentViewSet

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")
router.register("", ObligationViewSet, basename="obligation")

urlpatterns = router.urls
