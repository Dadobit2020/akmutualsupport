from rest_framework.routers import DefaultRouter
from .views import LedgerAccountViewSet, LedgerTransactionViewSet

router = DefaultRouter()
router.register("accounts", LedgerAccountViewSet, basename="ledger-account")
router.register("transactions", LedgerTransactionViewSet, basename="ledger-transaction")

urlpatterns = router.urls
