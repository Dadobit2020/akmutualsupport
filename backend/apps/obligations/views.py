from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Obligation, Payment
from .serializers import (
    ObligationSerializer,
    PaymentSerializer,
    ManualPaymentSerializer,
    WaiveObligationSerializer,
)
from .service import apply_payment, waive_obligation
from apps.identity.permissions import IsTreasurer, IsAdminRole
from apps.membership.models import Member


class ObligationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ObligationSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "member", "event", "obligation_type"]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return (
            Obligation.objects.filter(organization=org)
            .select_related("member", "event")
            .order_by("due_date")
        )

    @action(detail=True, methods=["post"], permission_classes=[IsTreasurer])
    def waive(self, request, pk=None):
        obligation = self.get_object()
        serializer = WaiveObligationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = waive_obligation(obligation, waived_by=request.user, reason=serializer.validated_data["reason"])
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ObligationSerializer(updated).data)


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsTreasurer]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["member", "method"]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return (
            Payment.objects.filter(organization=org)
            .select_related("member")
            .prefetch_related("applications")
            .order_by("-payment_date")
        )

    @action(detail=False, methods=["post"])
    def record_manual(self, request):
        """Record a manual/offline payment (check, cash, etc.)."""
        serializer = ManualPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        org = getattr(request, "organization", None)

        try:
            member = Member.objects.get(id=d["member"], organization=org)
        except Member.DoesNotExist:
            return Response({"detail": "Member not found."}, status=404)

        try:
            payment = apply_payment(
                organization=org,
                member=member,
                amount_cents=d["amount_cents"],
                payment_date=d["payment_date"],
                method=d["method"],
                reference=d.get("reference", ""),
                posted_by=request.user,
                notes=d.get("notes", ""),
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
