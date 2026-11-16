from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views, cbv_views, views
from .viewsets import TagViewSet, TournamentViewSet, VenueViewSet

app_name = "tournaments"

router = DefaultRouter()
router.register(r"venues", VenueViewSet, basename="venue")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"tournaments", TournamentViewSet, basename="tournament")

urlpatterns = [
    # 1. Tradycyjne widoki HTML (MVT)
    path("", views.tournament_list, name="list"),

    # 2. Endpointy widoków generycznych CBV (porównawczo)
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

    # 3. Profesjonalne REST API (ViewSets + DefaultRouter) pod api/v1/
    path("api/v1/", include(router.urls)),
    path(
        "api/v1/summary/",
        cbv_views.PlatformSummaryAPIView.as_view(),
        name="platform-summary",
    ),

    # 4. Legacy FBV z Lab 5 (dla kompatybilności wstecznej)
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
