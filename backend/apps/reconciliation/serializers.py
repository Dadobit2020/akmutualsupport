from rest_framework import serializers
from .models import ImportBatch, ImportedTransaction


class ImportBatchSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.CharField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = ImportBatch
        fields = [
            "id", "source", "original_filename", "status",
            "uploaded_by", "uploaded_by_email",
            "row_count", "matched_count", "applied_count",
            "error_message", "created_at",
        ]
        read_only_fields = ["id", "status", "row_count", "matched_count", "applied_count", "error_message", "created_at"]


class ImportBatchUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    source = serializers.ChoiceField(choices=["bank_csv", "tithely_csv"])


class ImportedTransactionSerializer(serializers.ModelSerializer):
    matched_member_name = serializers.SerializerMethodField()

    class Meta:
        model = ImportedTransaction
        fields = [
            "id", "batch", "transaction_date", "amount_cents",
            "payer_name", "memo", "raw_description", "source_reference",
            "match_status", "confidence_score",
            "matched_member", "matched_member_name",
            "matched_obligation", "match_explanation",
            "reviewed_by", "reviewed_at", "created_at",
        ]
        read_only_fields = ["id", "fingerprint", "created_at"]

    def get_matched_member_name(self, obj):
        if obj.matched_member:
            return obj.matched_member.get_full_name()
        return None


class ReviewTransactionSerializer(serializers.Serializer):
    """Confirm or correct a match during Treasurer review."""
    action = serializers.ChoiceField(choices=["apply", "reject", "reassign"])
    member_id = serializers.UUIDField(required=False)
    obligation_id = serializers.UUIDField(required=False)
