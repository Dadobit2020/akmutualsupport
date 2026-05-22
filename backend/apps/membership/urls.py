from rest_framework.routers import DefaultRouter
from .views import MemberViewSet, HouseholdViewSet, ContributionRuleViewSet

router = DefaultRouter()
router.register("households", HouseholdViewSet, basename="household")
router.register("contribution-rules", ContributionRuleViewSet, basename="contribution-rule")
router.register("", MemberViewSet, basename="member")

urlpatterns = router.urls
