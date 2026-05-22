from rest_framework import serializers
from .models import Obligation, Payment, PaymentApplication


class ObligationSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.get_full_name", read_only=True)
    outstanding_cents = serializers.IntegerField(read_only=True)
    event_description = serializers.SerializerMethodField()

    class Meta:
        model = Obligation
        fields = [
            "id", "obligation_type", "member", "member_name", "event", "event_description",
            "amount_cents", "paid_cents", "outstanding_cents", "due_date",
            "status", "waiver_reason", "notes", "created_at",
        ]
        read_only_fields = ["id", "paid_cents", "created_at"]

    def get_event_description(self, obj):
        if obj.event:
            return str(obj.event)
        return None


class PaymentApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentApplication
        fields = ["id", "obligation", "applied_cents"]


class PaymentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.get_full_name", read_only=True)
    applications = PaymentApplicationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "member", "member_name", "amount_cents", "payment_date",
            "method", "reference", "notes", "applications", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ManualPaymentSerializer(serializers.Serializer):
    member = serializers.UUIDField()
    amount_cents = serializers.IntegerField(min_value=1)
    payment_date = serializers.DateField()
    method = serializers.ChoiceField(choices=["check", "bank_transfer", "cash", "online", "other"])
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class WaiveObligationSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5)
