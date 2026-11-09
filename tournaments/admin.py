from django.contrib import admin

from .models import Match, Participant, Tag, Tournament, Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "capacity")
    search_fields = ("name", "city")
    list_filter = ("city",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organizer",
        "venue",
        "start_date",
        "max_participants",
        "is_online",
        "is_active",
    )
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("is_active", "is_online", "start_date", "venue")
    search_fields = ("name",)
    filter_horizontal = ("tags",)
    fieldsets = (
        (
            "Podstawowe informacje",
            {
                "fields": (
                    "name",
                    "slug",
                    "organizer",
                    "venue",
                    "tags",
                    "description",
                )
            },
        ),
        (
            "Organizacja",
            {
                "fields": (
                    "start_date",
                    "max_participants",
                    "entry_fee",
                    "is_online",
                    "is_active",
                )
            },
        ),
    )


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("nickname", "tournament", "user", "seed", "registered_at")
    list_filter = ("tournament",)
    search_fields = ("nickname", "user__username")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "tournament",
        "player_home",
        "player_away",
        "scheduled_at",
        "status",
        "home_legs",
        "away_legs",
        "winner",
    )
    list_filter = ("status", "tournament")
    search_fields = (
        "player_home__nickname",
        "player_away__nickname",
        "tournament__name",
    )
