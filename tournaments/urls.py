from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import cbv_views, views
from .viewsets import (
    MatchViewSet,
    ParticipantViewSet,
    TagViewSet,
    TournamentViewSet,
    VenueViewSet,
)

app_name = "tournaments"

router = DefaultRouter()
router.register(r"venues", VenueViewSet, basename="venue")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"tournaments", TournamentViewSet, basename="tournament")
router.register(r"participants", ParticipantViewSet, basename="participant")
router.register(r"matches", MatchViewSet, basename="match")

urlpatterns = [
    # 1. Tradycyjne widoki HTML (MVT)
    path("", views.tournament_list, name="list"),

    # 2. Endpointy widoków klasowych CBV (APIView oraz generics.* — porównawczo)
    path(
        "api/cbv/apiview/tournaments/",
        cbv_views.TournamentListAPIView.as_view(),
        name="apiview-tournament-list",
    ),
    path(
        "api/cbv/tournaments/",
        cbv_views.TournamentListCreateGenericView.as_view(),
        name="generic-tournament-list",
    ),
    path(
        "api/cbv/tournaments/<int:pk>/",
        cbv_views.TournamentRetrieveUpdateDestroyGenericView.as_view(),
        name="generic-tournament-detail",
    ),

    # 3. Docelowe REST API oparte na ModelViewSet + DefaultRouter pod api/v1/
    path("api/v1/", include(router.urls)),
    path(
        "api/v1/summary/",
        cbv_views.TournamentPlatformSummaryAPIView.as_view(),
        name="platform-summary",
    ),
]
