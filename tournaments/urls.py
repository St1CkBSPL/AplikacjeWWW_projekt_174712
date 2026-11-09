from django.urls import path

from . import api_views, views


app_name = "tournaments"

urlpatterns = [
    path("", views.tournament_list, name="list"),
    path(
        "api/tournaments/",
        api_views.tournament_list_create_api,
        name="api-tournament-list-create",
    ),
    path(
        "api/tournaments/<int:pk>/",
        api_views.tournament_detail_api,
        name="api-tournament-detail",
    ),
    path(
        "api/matches/",
        api_views.match_list_create_api,
        name="api-match-list-create",
    ),
    path(
        "api/matches/<int:pk>/",
        api_views.match_detail_api,
        name="api-match-detail",
    ),
]
