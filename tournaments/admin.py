from django.contrib import admin
from .models import Tournament, Participant


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'organizer', 'start_date', 'max_participants', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_active', 'start_date')
    search_fields = ('name',)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'tournament', 'user', 'seed', 'registered_at')
    list_filter = ('tournament',)
    search_fields = ('nickname', 'user__username')