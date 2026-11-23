from datetime import timedelta

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response

from .models import Match, Participant, Tag, Ticket, Tournament, Venue
from .serializers import (
    MatchSerializer,
    ParticipantSerializer,
    TagSerializer,
    TicketSerializer,
    TournamentListSerializer,
    TournamentModelSerializer,
    VenueSerializer,
)


def get_tournament_queryset():
    return (
        Tournament.objects.select_related("organizer", "venue")
        .prefetch_related("tags", "participants")
        .annotate(participants_count=Count("participants", distinct=True))
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
    def tournaments(self, request, pk=None):
        """Zwraca aktywne turnieje odbywające się w danym obiekcie."""
        venue = self.get_object()
        tournaments = get_tournament_queryset().filter(
            venue=venue,
            is_active=True,
        )
        serializer = TournamentListSerializer(tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TagViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla tagów."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    @action(detail=True, methods=["get"])
    def tournaments(self, request, pk=None):
        """Zwraca aktywne turnieje oznaczone danym tagiem."""
        tag = self.get_object()
        tournaments = get_tournament_queryset().filter(
            tags=tag,
            is_active=True,
        )
        serializer = TournamentListSerializer(tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ParticipantViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla uczestników turniejów."""

    queryset = Participant.objects.select_related("tournament", "user").all()
    serializer_class = ParticipantSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TournamentViewSet(viewsets.ModelViewSet):
    """
    Główny ModelViewSet dla turniejów darta z dynamicznym wyborem
    serializatora oraz niestandardowymi akcjami biznesowymi.
    """

    queryset = get_tournament_queryset()
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in ["list", "upcoming", "free_tournaments"]:
            return TournamentListSerializer
        return TournamentModelSerializer

    def perform_create(self, serializer):
        """Automatyczne przypisanie zalogowanego użytkownika jako organizatora."""
        serializer.save(organizer=self.request.user)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Zwraca aktywne turnieje zaplanowane w przyszłości."""
        upcoming_tournaments = (
            self.get_queryset()
            .filter(is_active=True, start_date__gte=timezone.now())
            .order_by("start_date")
        )
        serializer = self.get_serializer(upcoming_tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="free")
    def free_tournaments(self, request):
        """Zwraca aktywne, bezpłatne turnieje (entry_fee=0)."""
        free_qs = self.get_queryset().filter(is_active=True, entry_fee=0)
        serializer = self.get_serializer(free_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        """Przełącza status aktywności turnieju (is_active)."""
        tournament = self.get_object()
        tournament.is_active = not tournament.is_active
        tournament.save(update_fields=["is_active", "updated_at"])
        status_text = "aktywny" if tournament.is_active else "nieaktywny"
        return Response(
            {
                "message": (
                    f"Turniej '{tournament.name}' jest teraz {status_text}."
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
        """Tworzy kopię turnieju jako nieaktywny szkic na kolejny tydzień."""
        original = self.get_object()
        base_slug = (
            f"{original.slug[:120]}-kopia-{int(timezone.now().timestamp())}"
        )
        slug = base_slug
        counter = 1
        while Tournament.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        new_tournament = Tournament.objects.create(
            name=f"{original.name} (Kopia)",
            slug=slug,
            organizer=request.user,
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


class MatchViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla meczów darta + akcje domenowe."""

    serializer_class = MatchSerializer

    def get_queryset(self):
        queryset = Match.objects.select_related(
            "tournament",
            "player_home",
            "player_away",
            "winner",
            "player_home__user",
            "player_away__user",
        )
        tournament_id = self.request.query_params.get("tournament")
        if tournament_id:
            queryset = queryset.filter(tournament_id=tournament_id)
        return queryset

    @action(detail=False, methods=["get"])
    def live(self, request):
        """Zwraca aktualnie rozgrywane mecze (status=in_progress)."""
        live_matches = self.get_queryset().filter(
            status=Match.Status.IN_PROGRESS
        )
        serializer = self.get_serializer(live_matches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        """Zamyka mecz darta z końcowym wynikiem legów i ustala zwycięzcę."""
        dart_match = self.get_object()
        home_legs = request.data.get("home_legs")
        away_legs = request.data.get("away_legs")

        if home_legs is None or away_legs is None:
            return Response(
                {"error": "Pola 'home_legs' oraz 'away_legs' są wymagane."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            home_legs_int = int(home_legs)
            away_legs_int = int(away_legs)
        except (TypeError, ValueError):
            return Response(
                {"error": "Liczby legów muszą być liczbami całkowitymi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        winner_id = request.data.get("winner")
        if winner_id is None:
            if (
                home_legs_int == dart_match.legs_to_win
                and away_legs_int < dart_match.legs_to_win
            ):
                winner_id = dart_match.player_home_id
            elif (
                away_legs_int == dart_match.legs_to_win
                and home_legs_int < dart_match.legs_to_win
            ):
                winner_id = dart_match.player_away_id

        payload = {
            "home_legs": home_legs_int,
            "away_legs": away_legs_int,
            "winner": winner_id,
            "status": Match.Status.FINISHED,
        }
        serializer = self.get_serializer(dart_match, data=payload, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TicketViewSet(viewsets.ModelViewSet):
    """Endpoint biletów bieżącego użytkownika z izolacją danych (get_queryset)."""

    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user).select_related(
            "tournament",
            "tournament__venue",
            "user",
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
