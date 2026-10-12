from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Tournament(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nazwa turnieju")
    slug = models.SlugField(max_length=160, unique=True, verbose_name="Slug")
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="organized_tournaments", verbose_name="Organizator")
    start_date = models.DateTimeField(verbose_name="Data rozpoczęcia")
    max_participants = models.PositiveIntegerField(validators=[MinValueValidator(2)], verbose_name="Limit uczestników")
    is_active = models.BooleanField(default=True, verbose_name="Aktywny")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Turniej"
        verbose_name_plural = "Turnieje"
        ordering = ['start_date']

    def __str__(self):
        return self.name


class Participant(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="participants", verbose_name="Turniej")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tournament_participations", verbose_name="Użytkownik")
    nickname = models.CharField(max_length=50, verbose_name="Nick / Nazwa zawodnika")
    seed = models.PositiveIntegerField(default=1, verbose_name="Rozstawienie")
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Data rejestracji")

    class Meta:
        verbose_name = "Uczestnik"
        verbose_name_plural = "Uczestnicy"
        unique_together = ('tournament', 'user')

    def __str__(self):
        return f"{self.nickname} ({self.tournament.name})"