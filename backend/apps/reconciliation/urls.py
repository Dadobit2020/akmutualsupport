from rest_framework.routers import DefaultRouter
from .views import ImportBatchViewSet, ImportedTransactionViewSet

router = DefaultRouter()
router.register("batches", ImportBatchViewSet, basename="import-batch")
router.register("transactions", ImportedTransactionViewSet, basename="imported-transaction")

urlpatterns = router.urls
