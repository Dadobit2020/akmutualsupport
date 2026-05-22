from rest_framework import serializers
from .models import Event, EventOverride


class EventSerializer(serializers.ModelSerializer):
    affected_household_name = serializers.CharField(source="affected_household.name", read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "event_type", "affected_household", "affected_household_name",
            "event_date", "description", "payout_amount_cents", "status",
            "submitted_by", "submitted_by_name", "submitted_at",
            "approved_by", "approved_by_name", "approved_at",
            "rejection_reason", "contribution_deadline", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "submitted_by", "submitted_at",
            "approved_by", "approved_at", "contribution_deadline", "created_at", "updated_at",
        ]

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name()
        return None

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.get_full_name()
        return None


class EventApprovalSerializer(serializers.Serializer):
    pass


class EventRejectionSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10)


class EventReversalSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10)


class EventOverrideSerializer(serializers.ModelSerializer):
    applied_by_name = serializers.CharField(source="applied_by.get_full_name", read_only=True)

    class Meta:
        model = EventOverride
        fields = ["id", "event", "applied_by", "applied_by_name", "reason", "action", "created_at"]
        read_only_fields = ["id", "applied_by", "created_at"]
