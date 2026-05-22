import qrcode
import io
import base64
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .models import User, UserOrganizationRole, Role
from .serializers import (
    UserSerializer,
    UserRoleSerializer,
    MFASetupSerializer,
    PasswordChangeSerializer,
    CustomTokenObtainPairSerializer,
    OrganizationSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_setup_initiate(request):
    user = request.user
    if user.mfa_enabled:
        return Response({"detail": "MFA already enabled."}, status=400)
    secret = user.generate_mfa_secret()
    user.save(update_fields=["mfa_secret"])

    totp_uri = f"otpauth://totp/AddisKidan:{user.email}?secret={secret}&issuer=AddisKidan"
    qr = qrcode.make(totp_uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return Response({"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_setup_confirm(request):
    user = request.user
    serializer = MFASetupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if user.verify_mfa_token(serializer.validated_data["token"]):
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        return Response({"detail": "MFA enabled."})
    return Response({"detail": "Invalid token."}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_disable(request):
    user = request.user
    serializer = MFASetupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if user.verify_mfa_token(serializer.validated_data["token"]):
        user.mfa_enabled = False
        user.mfa_secret = ""
        user.save(update_fields=["mfa_enabled", "mfa_secret"])
        return Response({"detail": "MFA disabled."})
    return Response({"detail": "Invalid token."}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = request.user
    if not user.check_password(serializer.validated_data["current_password"]):
        return Response({"detail": "Current password incorrect."}, status=400)
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    return Response({"detail": "Password changed."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_user(request):
    """
    Admin-only. Creates a new user account (no password) linked to a member,
    assigns role, and triggers invite email with a one-time setup link.
    Body: { email, first_name, last_name, role, member_id? }
    """
    from apps.identity.permissions import IsAdminRole

    if not IsAdminRole().has_permission(request, None):
        return Response({"detail": "Permission denied."}, status=403)

    org = getattr(request, "organization", None)
    if not org:
        return Response({"detail": "No organization context."}, status=400)

    email = request.data.get("email", "").strip().lower()
    first_name = request.data.get("first_name", "").strip()
    last_name = request.data.get("last_name", "").strip()
    role = request.data.get("role", Role.MEMBER)
    member_id = request.data.get("member_id")

    if not email or not first_name or not last_name:
        return Response({"detail": "email, first_name, and last_name are required."}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({"detail": "A user with this email already exists."}, status=400)

    user = User.objects.create(
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    # No password — triggers invite email via signal

    UserOrganizationRole.objects.create(
        user=user,
        organization=org,
        role=role,
        granted_by=request.user,
    )

    if member_id:
        from apps.membership.models import Member
        try:
            member = Member.objects.get(id=member_id, organization=org)
            user.member = member
            user.save(update_fields=["member"])
        except Member.DoesNotExist:
            pass

    return Response(UserSerializer(user).data, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
def set_password(request):
    """
    One-time password setup from invite link.
    Body: { uid, token, password }
    """
    uid_b64 = request.data.get("uid", "")
    token = request.data.get("token", "")
    password = request.data.get("password", "")

    if not uid_b64 or not token or not password:
        return Response({"detail": "uid, token, and password are required."}, status=400)

    if len(password) < 12:
        return Response({"detail": "Password must be at least 12 characters."}, status=400)

    try:
        uid = force_str(urlsafe_base64_decode(uid_b64))
        user = User.objects.get(id=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response({"detail": "Invalid or expired link."}, status=400)

    generator = PasswordResetTokenGenerator()
    if not generator.check_token(user, token):
        return Response({"detail": "Invalid or expired link."}, status=400)

    from django.contrib.auth.password_validation import validate_password
    try:
        validate_password(password, user)
    except Exception as e:
        return Response({"detail": str(e)}, status=400)

    user.set_password(password)
    user.save(update_fields=["password"])
    return Response({"detail": "Password set. You can now log in."})
