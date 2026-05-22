from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Event, EventStatus
from .serializers import (
    EventSerializer,
    EventApprovalSerializer,
    EventRejectionSerializer,
    EventReversalSerializer,
)
from .service import submit_event_for_approval, approve_event, reject_event, reverse_event
from apps.identity.permissions import IsChairperson, IsAdminRole, IsTreasurer


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "event_type", "affected_household"]

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        return (
            Event.objects.filter(organization=org)
            .select_related("affected_household", "submitted_by", "approved_by")
            .order_by("-event_date")
        )

    def perform_create(self, serializer):
        org = getattr(self.request, "organization", None)
        serializer.save(organization=org)

    def get_permissions(self):
        if self.action in ("approve", "emergency_override"):
            return [IsAuthenticated(), IsChairperson()]
        if self.action in ("reverse",):
            return [IsAuthenticated(), IsTreasurer()]
        return super().get_permissions()

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        event = self.get_object()
        try:
            updated = submit_event_for_approval(event, submitted_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(EventSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        event = self.get_object()
        try:
            updated = approve_event(event, approved_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(EventSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        event = self.get_object()
        serializer = EventRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = reject_event(event, rejected_by=request.user, reason=serializer.validated_data["reason"])
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(EventSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        event = self.get_object()
        serializer = EventReversalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = reverse_event(event, reversed_by=request.user, reason=serializer.validated_data["reason"])
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(EventSerializer(updated).data)
