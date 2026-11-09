from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Match, Tournament
from .serializers import MatchSerializer, TournamentModelSerializer


def get_tournament_queryset():
    return (
        Tournament.objects.select_related("organizer", "venue")
        .prefetch_related("tags", "participants")
        .annotate(participants_count=Count("participants", distinct=True))
    )


def get_match_queryset():
    return Match.objects.select_related(
        "tournament",
        "player_home",
        "player_away",
        "winner",
        "player_home__user",
        "player_away__user",
    )


@api_view(["GET", "POST"])
def tournament_list_create_api(request):
    """GET: lista turniejów. POST: utworzenie turnieju po walidacji."""
    if request.method == "GET":
        tournaments = get_tournament_queryset()
        serializer = TournamentModelSerializer(tournaments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = TournamentModelSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
def tournament_detail_api(request, pk):
    """Szczegóły, pełna i częściowa aktualizacja oraz usunięcie turnieju."""
    tournament = get_object_or_404(get_tournament_queryset(), pk=pk)

    if request.method == "GET":
        serializer = TournamentModelSerializer(tournament)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "PUT":
        serializer = TournamentModelSerializer(tournament, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "PATCH":
        serializer = TournamentModelSerializer(
            tournament,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    tournament.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
def match_list_create_api(request):
    """GET: lista meczów. POST: utworzenie meczu po walidacji."""
    if request.method == "GET":
        matches = get_match_queryset()
        tournament_id = request.query_params.get("tournament")
        if tournament_id:
            matches = matches.filter(tournament_id=tournament_id)
        serializer = MatchSerializer(matches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = MatchSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
def match_detail_api(request, pk):
    """Szczegóły, pełna i częściowa aktualizacja oraz usunięcie meczu."""
    dart_match = get_object_or_404(get_match_queryset(), pk=pk)

    if request.method == "GET":
        serializer = MatchSerializer(dart_match)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "PUT":
        serializer = MatchSerializer(dart_match, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "PATCH":
        serializer = MatchSerializer(
            dart_match,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    dart_match.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
