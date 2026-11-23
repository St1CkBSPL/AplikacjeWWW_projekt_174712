from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Match, Participant, Tag, Tournament, Venue
from .serializers import (
    TournamentListSerializer,
    TournamentModelSerializer,
)


def get_tournament_queryset():
    return (
        Tournament.objects.select_related("organizer", "venue")
        .prefetch_related("tags", "participants")
        .annotate(participants_count=Count("participants", distinct=True))
    )


# --- PODEJŚCIE 1: Klasa bazowa APIView ---
class TournamentListAPIView(APIView):
    """Ręczna obsługa metod GET i POST wewnątrz klasy APIView."""

    def get(self, request):
        tournaments = get_tournament_queryset().filter(is_active=True)
        serializer = TournamentListSerializer(tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = TournamentModelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- PODEJŚCIE 2: Widoki generyczne (generics.*) ---
class TournamentListCreateGenericView(generics.ListCreateAPIView):
    """
    Automatycznie implementuje GET (lista) oraz POST (tworzenie).
    Używa lekkiego TournamentListSerializer dla GET i pełnego dla POST.
    """

    queryset = get_tournament_queryset()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return TournamentListSerializer
        return TournamentModelSerializer


class TournamentRetrieveUpdateDestroyGenericView(
    generics.RetrieveUpdateDestroyAPIView
):
    """Automatycznie implementuje GET (szczegóły), PUT, PATCH oraz DELETE."""

    queryset = get_tournament_queryset()
    serializer_class = TournamentModelSerializer


class TournamentPlatformSummaryAPIView(APIView):
    """Endpoint agregujący statystyki platformy turniejowej (APIView)."""

    def get(self, request):
        now = timezone.now()
        active_tournaments = Tournament.objects.filter(is_active=True)

        tournament_stats = Tournament.objects.aggregate(
            total_tournaments=Count("id"),
            active_tournaments=Count("id", filter=Q(is_active=True)),
            upcoming_tournaments=Count(
                "id",
                filter=Q(is_active=True, start_date__gte=now),
            ),
            free_tournaments=Count(
                "id",
                filter=Q(is_active=True, entry_fee=0),
            ),
        )
        fee_stats = active_tournaments.aggregate(
            average_entry_fee=Avg("entry_fee"),
            min_entry_fee=Min("entry_fee"),
            max_entry_fee=Max("entry_fee"),
        )
        match_stats = Match.objects.aggregate(
            matches_count=Count("id"),
            finished_matches_count=Count(
                "id",
                filter=Q(status=Match.Status.FINISHED),
            ),
            live_matches_count=Count(
                "id",
                filter=Q(status=Match.Status.IN_PROGRESS),
            ),
        )

        def fmt_decimal(value):
            return round(float(value), 2) if value is not None else 0.00

        return Response(
            {
                **tournament_stats,
                "venues_count": Venue.objects.count(),
                "tags_count": Tag.objects.count(),
                "participants_count": Participant.objects.count(),
                **match_stats,
                "average_entry_fee": fmt_decimal(
                    fee_stats["average_entry_fee"]
                ),
                "min_entry_fee": fmt_decimal(fee_stats["min_entry_fee"]),
                "max_entry_fee": fmt_decimal(fee_stats["max_entry_fee"]),
            },
            status=status.HTTP_200_OK,
        )
