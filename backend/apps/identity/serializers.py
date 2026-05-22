from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, UserOrganizationRole, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "currency", "timezone",
            "default_payout_amount_cents", "contribution_deadline_days",
            "contact_email", "phone",
        ]
        read_only_fields = ["id"]


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "mfa_enabled", "is_active"]
        read_only_fields = ["id", "mfa_enabled"]


class UserRoleSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = UserOrganizationRole
        fields = ["id", "user", "user_email", "role", "is_active"]
        read_only_fields = ["id"]


class MFASetupSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6, min_length=6)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=12)

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    mfa_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if user.mfa_enabled:
            mfa_token = attrs.get("mfa_token", "")
            if not mfa_token:
                raise serializers.ValidationError({"mfa_token": "MFA token required."})
            if not user.verify_mfa_token(mfa_token):
                raise serializers.ValidationError({"mfa_token": "Invalid MFA token."})
        data["user"] = UserSerializer(user).data
        return data
