from django.db.models import Avg
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tag, Tournament, Venue
from .serializers import (
    TournamentListSerializer,
    TournamentModelSerializer,
)


# --- PODEJŚCIE 1: Klasa bazowa APIView ---
class TournamentListAPIView(APIView):
    """
    Ręczna obsługa metod GET i POST wewnątrz klasy APIView.
    """

    def get(self, request):
        tournaments = (
            Tournament.objects.filter(is_active=True)
            .select_related("venue", "organizer")
            .prefetch_related("tags")
        )
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
    Metoda get_serializer_class pozwala użyć lżejszego serializatora dla GET.
    """

    queryset = (
        Tournament.objects.select_related("venue", "organizer")
        .prefetch_related("tags")
        .all()
    )

    def get_serializer_class(self):
        if self.request.method == "GET":
            return TournamentListSerializer
        return TournamentModelSerializer


class TournamentRetrieveUpdateDestroyGenericView(
    generics.RetrieveUpdateDestroyAPIView
):
    """
    Automatycznie implementuje GET (szczegóły), PUT, PATCH oraz DELETE.
    """

    queryset = (
        Tournament.objects.select_related("venue", "organizer")
        .prefetch_related("tags")
        .all()
    )
    serializer_class = TournamentModelSerializer


class PlatformSummaryAPIView(APIView):
    """Endpoint agregujący statystyki platformy turniejowej."""

    def get(self, request):
        published = Tournament.objects.filter(is_active=True)
        total_published_events = published.count()
        upcoming_events_count = published.filter(
            start_date__gte=timezone.now()
        ).count()
        free_events_count = published.filter(entry_fee=0).count()
        categories_count = Venue.objects.count()
        tags_count = Tag.objects.count()

        avg_price = published.aggregate(avg=Avg("entry_fee"))["avg"]
        average_ticket_price = (
            round(float(avg_price), 2) if avg_price is not None else 0.00
        )

        return Response(
            {
                "total_published_events": total_published_events,
                "upcoming_events_count": upcoming_events_count,
                "free_events_count": free_events_count,
                "categories_count": categories_count,
                "tags_count": tags_count,
                "average_ticket_price": average_ticket_price,
            },
            status=status.HTTP_200_OK,
        )
