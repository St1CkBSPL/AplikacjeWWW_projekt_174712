from django.shortcuts import render
from django.db.models import Count

from .models import Tournament


def tournament_list(request):
    """Wyświetla turnieje wraz z organizatorem i liczbą uczestników."""
    tournaments = (
        Tournament.objects.select_related("organizer", "venue")
        .prefetch_related("tags")
        .annotate(participants_count=Count("participants", distinct=True))
    )
    return render(
        request,
        "tournaments/tournament_list.html",
        {"tournaments": tournaments},
    )
