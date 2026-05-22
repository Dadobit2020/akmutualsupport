from rest_framework import serializers
from .models import Member, Household, ContributionRule, HouseholdMembershipHistory


class ContributionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributionRule
        fields = ["id", "name", "contribution_type", "fraction", "fixed_cap_cents", "description", "is_active"]
        read_only_fields = ["id"]


class HouseholdSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Household
        fields = ["id", "name", "primary_contact", "emergency_contact_name", "emergency_contact_phone", "member_count"]
        read_only_fields = ["id"]

    def get_member_count(self, obj):
        return obj.members.filter(status="active").count()


class MemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    household_name = serializers.CharField(source="household.name", read_only=True)
    contribution_rule_name = serializers.CharField(source="contribution_rule.name", read_only=True)

    class Meta:
        model = Member
        fields = [
            "id", "first_name", "last_name", "first_name_am", "last_name_am",
            "full_name", "household", "household_name", "status", "tier",
            "contribution_rule", "contribution_rule_name", "join_date", "leave_date",
            "email", "phone", "phone_whatsapp", "preferred_language", "address",
            "payment_reference", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MemberListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    household_name = serializers.CharField(source="household.name", read_only=True)

    class Meta:
        model = Member
        fields = ["id", "full_name", "first_name", "last_name", "household_name", "status", "tier", "email", "phone"]


class HouseholdMembershipHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseholdMembershipHistory
        fields = ["id", "member", "household", "joined_on", "left_on", "reason", "created_at"]
        read_only_fields = ["id", "created_at"]
