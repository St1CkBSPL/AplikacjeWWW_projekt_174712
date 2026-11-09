from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Venue(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nazwa obiektu")
    city = models.CharField(max_length=100, verbose_name="Miasto")
    address = models.CharField(max_length=255, blank=True, verbose_name="Adres")
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(2)],
        verbose_name="Pojemność obiektu",
    )

    class Meta:
        verbose_name = "Obiekt"
        verbose_name_plural = "Obiekty"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.city})"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Nazwa tagu")
    slug = models.SlugField(max_length=60, unique=True, verbose_name="Slug tagu")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tagi"
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"


class Tournament(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nazwa turnieju")
    slug = models.SlugField(max_length=160, unique=True, verbose_name="Slug")
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organized_tournaments",
        verbose_name="Organizator",
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name="tournaments",
        null=True,
        blank=True,
        verbose_name="Obiekt",
    )
    tags = models.ManyToManyField(
        Tag,
        related_name="tournaments",
        blank=True,
        verbose_name="Tagi tematyczne",
    )
    description = models.TextField(blank=True, verbose_name="Opis turnieju")
    start_date = models.DateTimeField(verbose_name="Data rozpoczęcia")
    max_participants = models.PositiveIntegerField(
        validators=[MinValueValidator(2)],
        verbose_name="Limit uczestników",
    )
    entry_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name="Wpisowe (PLN)",
    )
    is_online = models.BooleanField(default=False, verbose_name="Turniej online")
    is_active = models.BooleanField(default=True, verbose_name="Aktywny")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Turniej"
        verbose_name_plural = "Turnieje"
        ordering = ["start_date"]

    def __str__(self):
        return self.name


class Participant(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Turniej",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tournament_participations",
        verbose_name="Użytkownik",
    )
    nickname = models.CharField(max_length=50, verbose_name="Nick / Nazwa zawodnika")
    seed = models.PositiveIntegerField(default=1, verbose_name="Rozstawienie")
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Data rejestracji")

    class Meta:
        verbose_name = "Uczestnik"
        verbose_name_plural = "Uczestnicy"
        unique_together = ("tournament", "user")

    def __str__(self):
        return f"{self.nickname} ({self.tournament.name})"


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Zaplanowany"
        IN_PROGRESS = "in_progress", "W trakcie"
        FINISHED = "finished", "Zakończony"
        CANCELLED = "cancelled", "Anulowany"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="matches",
        verbose_name="Turniej",
    )
    player_home = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="home_matches",
        verbose_name="Zawodnik gospodarzy",
    )
    player_away = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="away_matches",
        verbose_name="Zawodnik gości",
    )
    winner = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        related_name="won_matches",
        null=True,
        blank=True,
        verbose_name="Zwycięzca",
    )
    scheduled_at = models.DateTimeField(verbose_name="Termin meczu")
    legs_to_win = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        verbose_name="Liczba legów do zwycięstwa",
    )
    home_legs = models.PositiveIntegerField(default=0, verbose_name="Legi gospodarza")
    away_legs = models.PositiveIntegerField(default=0, verbose_name="Legi gościa")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name="Status",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mecz"
        verbose_name_plural = "Mecze"
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.player_home.nickname} vs {self.player_away.nickname}"
