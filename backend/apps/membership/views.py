from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.identity.permissions import IsAdminRole
from .models import Member, Household, ContributionRule
from .serializers import (
    MemberSerializer,
    MemberListSerializer,
    HouseholdSerializer,
    ContributionRuleSerializer,
)


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.select_related("household", "contribution_rule").order_by("last_name", "first_name")
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "tier", "household"]
    search_fields = ["first_name", "last_name", "email", "phone", "payment_reference"]
    ordering_fields = ["last_name", "first_name", "join_date", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return MemberListSerializer
        return MemberSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org = getattr(self.request, "organization", None)
        serializer.save(organization=org)


class HouseholdViewSet(viewsets.ModelViewSet):
    queryset = Household.objects.prefetch_related("members").order_by("name")
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = HouseholdSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org = getattr(self.request, "organization", None)
        serializer.save(organization=org)


class ContributionRuleViewSet(viewsets.ModelViewSet):
    queryset = ContributionRule.objects.filter(is_active=True).order_by("name")
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = ContributionRuleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org = getattr(self.request, "organization", None)
        serializer.save(organization=org)
