from rest_framework import serializers
from .models import LedgerAccount, LedgerTransaction, LedgerEntry


class LedgerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerAccount
        fields = ["id", "code", "name", "account_type", "description", "is_active"]
        read_only_fields = ["id"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = LedgerEntry
        fields = [
            "id", "account", "account_code", "account_name",
            "debit_cents", "credit_cents", "description",
            "member", "member_name", "obligation", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_member_name(self, obj):
        if obj.member:
            return obj.member.get_full_name()
        return None


class LedgerTransactionSerializer(serializers.ModelSerializer):
    entries = LedgerEntrySerializer(many=True, read_only=True)
    posted_by_email = serializers.CharField(source="posted_by.email", read_only=True)

    class Meta:
        model = LedgerTransaction
        fields = [
            "id", "description", "transaction_date", "source",
            "posted_by", "posted_by_email", "event", "reverses",
            "notes", "entries", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
