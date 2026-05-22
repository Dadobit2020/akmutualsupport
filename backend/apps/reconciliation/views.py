from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import ImportBatch, ImportedTransaction, MatchStatus
from .serializers import (
    ImportBatchSerializer,
    ImportBatchUploadSerializer,
    ImportedTransactionSerializer,
    ReviewTransactionSerializer,
)
from .tasks import process_import_batch
from apps.identity.permissions import IsTreasurer
from apps.membership.models import Member
from apps.obligations.models import Obligation
from apps.obligations.service import apply_payment


class ImportBatchViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ImportBatchSerializer
    permission_classes = [IsAuthenticated, IsTreasurer]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return ImportBatch.objects.filter(organization=org).order_by("-created_at")

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def upload(self, request):
        serializer = ImportBatchUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = getattr(request, "organization", None)
        uploaded_file = serializer.validated_data["file"]

        batch = ImportBatch.objects.create(
            organization=org,
            source=serializer.validated_data["source"],
            file=uploaded_file,
            original_filename=uploaded_file.name,
            uploaded_by=request.user,
        )

        process_import_batch.delay(str(batch.id))

        return Response(ImportBatchSerializer(batch).data, status=status.HTTP_202_ACCEPTED)


class ImportedTransactionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ImportedTransactionSerializer
    permission_classes = [IsAuthenticated, IsTreasurer]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["match_status", "batch"]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return (
            ImportedTransaction.objects.filter(organization=org)
            .select_related("batch", "matched_member", "matched_obligation")
            .order_by("-transaction_date")
        )

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Treasurer confirms, rejects, or reassigns a match."""
        txn = self.get_object()
        serializer = ReviewTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        org = getattr(request, "organization", None)

        if txn.match_status == MatchStatus.APPLIED:
            return Response({"detail": "Transaction already applied."}, status=400)

        action_type = d["action"]

        if action_type == "reject":
            txn.match_status = MatchStatus.REJECTED
            txn.reviewed_by = request.user
            txn.reviewed_at = timezone.now()
            txn.save(update_fields=["match_status", "reviewed_by", "reviewed_at", "updated_at"])
            return Response({"detail": "Transaction rejected."})

        # Resolve member
        member = txn.matched_member
        if d.get("member_id"):
            try:
                member = Member.objects.get(id=d["member_id"], organization=org)
            except Member.DoesNotExist:
                return Response({"detail": "Member not found."}, status=404)

        if not member:
            return Response({"detail": "No member specified for application."}, status=400)

        try:
            apply_payment(
                organization=org,
                member=member,
                amount_cents=txn.amount_cents,
                payment_date=txn.transaction_date,
                method="bank_transfer",
                reference=txn.source_reference,
                posted_by=request.user,
                imported_transaction=txn,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        txn.matched_member = member
        txn.match_status = MatchStatus.APPLIED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.save(update_fields=["matched_member", "match_status", "reviewed_by", "reviewed_at", "updated_at"])

        return Response({"detail": "Payment applied."})
