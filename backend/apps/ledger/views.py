from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import LedgerAccount, LedgerTransaction, LedgerEntry
from .serializers import LedgerAccountSerializer, LedgerTransactionSerializer
from .service import post_reversal, get_member_balance_cents
from apps.identity.permissions import IsTreasurer


class LedgerAccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LedgerAccountSerializer
    permission_classes = [IsAuthenticated, IsTreasurer]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return LedgerAccount.objects.filter(organization=org, is_active=True).order_by("code")


class LedgerTransactionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = LedgerTransactionSerializer
    permission_classes = [IsAuthenticated, IsTreasurer]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source", "event"]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return (
            LedgerTransaction.objects.filter(organization=org)
            .select_related("posted_by", "event")
            .prefetch_related("entries__account", "entries__member")
            .order_by("-transaction_date", "-created_at")
        )

    @action(detail=True, methods=["post"], permission_classes=[IsTreasurer])
    def reverse(self, request, pk=None):
        txn = self.get_object()
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "A reason is required for reversals."}, status=400)
        if hasattr(txn, "reversed_by"):
            return Response({"detail": "This transaction has already been reversed."}, status=400)
        reversal = post_reversal(original_txn=txn, posted_by=request.user, reason=reason)
        return Response(self.get_serializer(reversal).data, status=status.HTTP_201_CREATED)
