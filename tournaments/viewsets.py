from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Tag, Tournament, Venue
from .serializers import (
    TagSerializer,
    TournamentListSerializer,
    TournamentModelSerializer,
    VenueSerializer,
)


class VenueViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla obiektów (Venue)."""

    queryset = Venue.objects.all()
    serializer_class = VenueSerializer

    def destroy(self, request, *args, **kwargs):
        """Blokada usunięcia obiektu, który posiada przypisane turnieje."""
        venue = self.get_object()
        if venue.tournaments.exists():
            return Response(
                {
                    "error": (
                        "Nie można usunąć obiektu, do którego są "
                        "przypisane turnieje."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        """Zwraca aktywne turnieje przypisane do danego obiektu."""
        venue = self.get_object()
        tournaments = (
            venue.tournaments.filter(is_active=True)
            .select_related("venue", "organizer")
            .prefetch_related("tags")
        )
        serializer = TournamentListSerializer(tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TagViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla tagów."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        """Zwraca aktywne turnieje posiadające dany tag."""
        tag = self.get_object()
        tournaments = (
            tag.tournaments.filter(is_active=True)
            .select_related("venue", "organizer")
            .prefetch_related("tags")
        )
        serializer = TournamentListSerializer(tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TournamentViewSet(viewsets.ModelViewSet):
    """
    Kompletny zestaw operacji CRUD dla turniejów z dynamicznym wyborem
    serializatora oraz niestandardowymi akcjami biznesowymi.
    """

    queryset = (
        Tournament.objects.select_related("venue", "organizer")
        .prefetch_related("tags")
        .all()
    )

    def get_serializer_class(self):
        if self.action in ["list", "upcoming", "free_events"]:
            return TournamentListSerializer
        return TournamentModelSerializer

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Zwraca wyłącznie aktywne turnieje z datą w przyszłości."""
        upcoming_tournaments = (
            self.get_queryset()
            .filter(is_active=True, start_date__gte=timezone.now())
            .order_by("start_date")
        )
        serializer = self.get_serializer(upcoming_tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def free_events(self, request):
        """Zwraca aktywne, bezpłatne turnieje (entry_fee=0)."""
        free_tournaments = self.get_queryset().filter(
            is_active=True,
            entry_fee=0,
        )
        serializer = self.get_serializer(free_tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def publish_toggle(self, request, pk=None):
        """Przełącza status aktywności turnieju (is_active)."""
        tournament = self.get_object()
        tournament.is_active = not tournament.is_active
        tournament.save(update_fields=["is_active", "updated_at"])
        status_text = "aktywny" if tournament.is_active else "ukryty"
        return Response(
            {
                "message": (
                    f"Turniej '{tournament.name}' został oznaczony jako "
                    f"{status_text}."
                ),
                "is_active": tournament.is_active,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post", "delete"], url_path="manage-tags")
    def manage_tags(self, request, pk=None):
        """Dopina (POST) lub odpina (DELETE) pojedynczy tag od turnieju."""
        tournament = self.get_object()
        tag_id = request.data.get("tag_id")
        if tag_id is None:
            return Response(
                {"error": "Pole 'tag_id' jest wymagane."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tag = get_object_or_404(Tag, pk=tag_id)

        if request.method == "POST":
            tournament.tags.add(tag)
        elif request.method == "DELETE":
            tournament.tags.remove(tag)

        return Response(
            TagSerializer(tournament.tags.all(), many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Tworzy kopię turnieju jako szkic na kolejny tydzień."""
        original = self.get_object()
        new_tournament = Tournament.objects.create(
            name=f"{original.name} (Kopia)",
            slug=f"{original.slug}-kopia-{int(timezone.now().timestamp())}",
            organizer=original.organizer,
            venue=original.venue,
            description=original.description,
            start_date=original.start_date + timedelta(days=7),
            max_participants=original.max_participants,
            entry_fee=original.entry_fee,
            is_online=original.is_online,
            is_active=False,
        )
        new_tournament.tags.set(original.tags.all())
        serializer = TournamentModelSerializer(new_tournament)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
