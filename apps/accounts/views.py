from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.models import AuditAction
from apps.audit.services import diff, record

from .models import User
from .permissions import IsAdmin
from .serializers import (
    AdminUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .verification import send_verification_email, user_from_token


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Admin-only user management. Users are deactivated rather than deleted."""

    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["id", "email", "date_joined"]

    def perform_create(self, serializer):
        user = serializer.save()
        record(AuditAction.USER_CREATED, request=self.request, target=user,
               changes={"email": user.email, "role": user.role})

    def perform_update(self, serializer):
        changes = diff(serializer.instance, serializer.validated_data)
        user = serializer.save()
        if changes:
            record(AuditAction.USER_UPDATED, request=self.request, target=user, changes=changes)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        record(AuditAction.USER_REGISTERED, request=self.request, actor=user, target=user)
        send_verification_email(user, self.request)


class VerifyEmailView(APIView):
    """Confirm an email address. GET works straight from the emailed link; POST takes the token in the body."""

    permission_classes = [AllowAny]
    serializer_class = VerifyEmailSerializer

    @extend_schema(parameters=[OpenApiParameter("token", str, required=True)], responses={200: None})
    def get(self, request):
        return self._verify(request.query_params.get("token", ""))

    @extend_schema(request=VerifyEmailSerializer, responses={200: None})
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._verify(serializer.validated_data["token"])

    def _verify(self, token):
        user = user_from_token(token)
        if user is None:
            return Response({"detail": "Invalid or expired verification link."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
            record(AuditAction.EMAIL_VERIFIED, request=self.request, actor=user, target=user)
        return Response({"detail": "Email verified. You can now log in."})


class ResendVerificationView(APIView):
    """Send a fresh verification link. Always answers the same way to avoid revealing accounts."""

    permission_classes = [AllowAny]
    serializer_class = ResendVerificationSerializer

    @extend_schema(request=ResendVerificationSerializer, responses={200: None})
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_email_verified=False, is_active=True
        ).first()
        if user:
            send_verification_email(user, request)
        return Response({"detail": "If the account exists and is unverified, a new link has been sent."})


class MeView(generics.RetrieveUpdateAPIView):
    """The authenticated user's own profile. Role and email are read-only here."""

    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as exc:
            record(AuditAction.LOGIN_FAILED, request=request,
                   changes={"email": str(request.data.get("email", ""))[:254],
                            "reason": exc.get_codes()})
            raise
        record(AuditAction.LOGIN_SUCCEEDED, request=request, actor=serializer.user, target=serializer.user)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Blacklists the given refresh token so it can no longer be used."""

    serializer_class = LogoutSerializer

    @extend_schema(responses={205: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)
