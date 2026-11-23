from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Match,
    OrganizerProfile,
    Participant,
    Tag,
    Ticket,
    Tournament,
    Venue,
)


class TournamentSerializer(serializers.Serializer):
    """Ręczny serializator modelu Tournament (Lab 4)."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(required=True, max_length=150)
    slug = serializers.SlugField(required=True, max_length=160)
    organizer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="organizer",
    )
    start_date = serializers.DateTimeField(required=True)
    max_participants = serializers.IntegerField(required=True, min_value=2)
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        return Tournament.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.slug = validated_data.get("slug", instance.slug)
        instance.organizer = validated_data.get("organizer", instance.organizer)
        instance.start_date = validated_data.get(
            "start_date",
            instance.start_date,
        )
        instance.max_participants = validated_data.get(
            "max_participants",
            instance.max_participants,
        )
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()
        return instance


class TagSerializer(serializers.ModelSerializer):
    tournaments_count = serializers.IntegerField(
        source="tournaments.count",
        read_only=True,
    )

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "tournaments_count"]
        read_only_fields = ["id", "tournaments_count"]


class VenueSerializer(serializers.ModelSerializer):
    tournaments_count = serializers.IntegerField(
        source="tournaments.count",
        read_only=True,
    )

    class Meta:
        model = Venue
        fields = [
            "id",
            "name",
            "city",
            "address",
            "capacity",
            "tournaments_count",
        ]
        read_only_fields = ["id", "tournaments_count"]


class ParticipantSerializer(serializers.ModelSerializer):
    tournament_name = serializers.ReadOnlyField(source="tournament.name")
    user_username = serializers.ReadOnlyField(source="user.username")
    matches_played = serializers.SerializerMethodField()
    is_top_seed = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = [
            "id",
            "tournament",
            "tournament_name",
            "user",
            "user_username",
            "nickname",
            "seed",
            "registered_at",
            "matches_played",
            "is_top_seed",
        ]
        read_only_fields = ["id", "user", "registered_at"]

    def get_matches_played(self, obj) -> int:
        return obj.home_matches.count() + obj.away_matches.count()

    def get_is_top_seed(self, obj) -> bool:
        return obj.seed == 1


class TournamentListSerializer(serializers.ModelSerializer):
    """Lekki serializator listy turniejów dla akcji list/upcoming/free."""

    organizer_username = serializers.ReadOnlyField(source="organizer.username")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    is_free = serializers.SerializerMethodField()
    short_description = serializers.SerializerMethodField()
    tags_count = serializers.SerializerMethodField()
    seats_left = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            "id",
            "name",
            "slug",
            "venue_name",
            "organizer_username",
            "start_date",
            "max_participants",
            "entry_fee",
            "is_online",
            "is_active",
            "is_free",
            "short_description",
            "tags_count",
            "seats_left",
        ]

    def get_is_free(self, obj) -> bool:
        return obj.entry_fee == 0

    def get_short_description(self, obj) -> str:
        description = obj.description or ""
        if len(description) > 80:
            return f"{description[:80]}..."
        return description

    def get_tags_count(self, obj) -> int:
        return len(obj.tags.all())

    def get_seats_left(self, obj) -> int:
        participants_count = getattr(obj, "participants_count", None)
        if participants_count is None:
            participants_count = obj.participants.count()
        return max(0, obj.max_participants - participants_count)


class TournamentModelSerializer(serializers.ModelSerializer):
    organizer_username = serializers.ReadOnlyField(source="organizer.username")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    tags_details = TagSerializer(source="tags", many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        source="tags",
        write_only=True,
        required=False,
    )
    is_free = serializers.SerializerMethodField()
    days_until_start = serializers.SerializerMethodField()
    seats_left = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            "id",
            "name",
            "slug",
            "organizer",
            "organizer_username",
            "venue",
            "venue_name",
            "tags_details",
            "tag_ids",
            "description",
            "start_date",
            "max_participants",
            "entry_fee",
            "is_online",
            "is_active",
            "is_free",
            "days_until_start",
            "seats_left",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organizer", "created_at", "updated_at"]

    def get_is_free(self, obj) -> bool:
        return obj.entry_fee == 0

    def get_days_until_start(self, obj) -> int:
        delta = obj.start_date - timezone.now()
        return max(0, delta.days)

    def get_seats_left(self, obj) -> int:
        participants_count = getattr(obj, "participants_count", None)
        if participants_count is None:
            participants_count = obj.participants.count()
        return max(0, obj.max_participants - participants_count)

    def validate_start_date(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Termin turnieju musi być datą w przyszłości!"
            )
        return value

    def validate_max_participants(self, value):
        if value % 2 != 0:
            raise serializers.ValidationError(
                "Limit uczestników musi być liczbą parzystą (drabinka pucharowa)."
            )
        return value

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        description = attrs.get(
            "description",
            getattr(self.instance, "description", ""),
        )
        entry_fee = attrs.get(
            "entry_fee",
            getattr(self.instance, "entry_fee", Decimal("0.00")),
        )
        is_active = attrs.get(
            "is_active",
            getattr(self.instance, "is_active", True),
        )
        is_online = attrs.get(
            "is_online",
            getattr(self.instance, "is_online", False),
        )
        venue = attrs.get("venue", getattr(self.instance, "venue", None))
        max_participants = attrs.get(
            "max_participants",
            getattr(self.instance, "max_participants", None),
        )

        if (
            any(word in name.lower() for word in ["darmow", "bezpłatn", "free"])
            and entry_fee > 0
        ):
            raise serializers.ValidationError(
                {
                    "entry_fee": (
                        "Turniej oznaczony w nazwie jako bezpłatny nie może "
                        "mieć wpisowego wyższego niż 0.00 PLN."
                    )
                }
            )

        if is_active and len(description.strip()) < 20:
            raise serializers.ValidationError(
                {
                    "description": (
                        "Aktywny turniej musi posiadać opis (minimum 20 znaków)."
                    )
                }
            )

        if is_online:
            if venue is not None:
                raise serializers.ValidationError(
                    {
                        "venue": (
                            "Turniej online nie może mieć przypisanego obiektu stacjonarnego."
                        )
                    }
                )
            if max_participants and max_participants > 128:
                raise serializers.ValidationError(
                    {
                        "max_participants": (
                            "Turniej online może mieć maksymalnie 128 uczestników."
                        )
                    }
                )
        else:
            if venue is None:
                raise serializers.ValidationError(
                    {
                        "venue": (
                            "Turniej stacjonarny wymaga wskazania obiektu."
                        )
                    }
                )
            if (
                max_participants is not None
                and venue is not None
                and max_participants > venue.capacity
            ):
                raise serializers.ValidationError(
                    {
                        "max_participants": (
                            "Limit uczestników nie może przekraczać pojemności obiektu."
                        )
                    }
                )

        return attrs


class MatchSerializer(serializers.ModelSerializer):
    tournament_name = serializers.ReadOnlyField(source="tournament.name")
    player_home_nickname = serializers.ReadOnlyField(source="player_home.nickname")
    player_away_nickname = serializers.ReadOnlyField(source="player_away.nickname")
    winner_nickname = serializers.ReadOnlyField(source="winner.nickname")
    is_finished = serializers.SerializerMethodField()
    scoreline = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "tournament",
            "tournament_name",
            "player_home",
            "player_home_nickname",
            "player_away",
            "player_away_nickname",
            "winner",
            "winner_nickname",
            "scheduled_at",
            "legs_to_win",
            "home_legs",
            "away_legs",
            "status",
            "is_finished",
            "scoreline",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_finished(self, obj) -> bool:
        return obj.status == Match.Status.FINISHED

    def get_scoreline(self, obj) -> str:
        return f"{obj.home_legs}:{obj.away_legs}"

    def validate(self, attrs):
        tournament = attrs.get(
            "tournament",
            getattr(self.instance, "tournament", None),
        )
        player_home = attrs.get(
            "player_home",
            getattr(self.instance, "player_home", None),
        )
        player_away = attrs.get(
            "player_away",
            getattr(self.instance, "player_away", None),
        )
        winner = attrs.get("winner", getattr(self.instance, "winner", None))
        status = attrs.get(
            "status",
            getattr(self.instance, "status", Match.Status.SCHEDULED),
        )
        home_legs = attrs.get(
            "home_legs",
            getattr(self.instance, "home_legs", 0),
        )
        away_legs = attrs.get(
            "away_legs",
            getattr(self.instance, "away_legs", 0),
        )
        legs_to_win = attrs.get(
            "legs_to_win",
            getattr(self.instance, "legs_to_win", 3),
        )

        if player_home and player_away and player_home == player_away:
            raise serializers.ValidationError(
                {
                    "player_away": (
                        "Zawodnik gospodarzy i gości musi być różny."
                    )
                }
            )

        if (
            tournament
            and player_home
            and player_home.tournament_id != tournament.id
        ):
            raise serializers.ValidationError(
                {
                    "player_home": (
                        "Zawodnik gospodarzy musi należeć do tego samego turnieju."
                    )
                }
            )

        if (
            tournament
            and player_away
            and player_away.tournament_id != tournament.id
        ):
            raise serializers.ValidationError(
                {
                    "player_away": (
                        "Zawodnik gości musi należeć do tego samego turnieju."
                    )
                }
            )

        if winner and winner not in (player_home, player_away):
            raise serializers.ValidationError(
                {
                    "winner": (
                        "Zwycięzca musi być jednym z zawodników tego meczu."
                    )
                }
            )

        if status == Match.Status.FINISHED:
            if winner is None:
                raise serializers.ValidationError(
                    {
                        "winner": "Zakończony mecz wymaga wskazania zwycięzcy."
                    }
                )
            if home_legs != legs_to_win and away_legs != legs_to_win:
                raise serializers.ValidationError(
                    {
                        "home_legs": (
                            "W zakończonym meczu jeden z zawodników musi "
                            "osiągnąć wymaganą liczbę legów."
                        )
                    }
                )

        return attrs


class OrganizerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizerProfile
        fields = ["company_name", "bio", "website", "is_verified"]
        read_only_fields = ["is_verified"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    company_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "company_name",
        ]

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Użytkownik z tym adresem e-mail już istnieje."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Podane hasła nie są identyczne."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        company_name = validated_data.pop("company_name", "")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        OrganizerProfile.objects.create(user=user, company_name=company_name)
        return user


class CurrentUserSerializer(serializers.ModelSerializer):
    profile = OrganizerProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "profile",
        ]
        read_only_fields = ["id", "username", "date_joined"]

    def validate_email(self, value):
        if (
            value
            and User.objects.filter(email__iexact=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "Użytkownik z tym adresem e-mail już istnieje."
            )
        return value

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None:
            profile, _ = OrganizerProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class TicketSerializer(serializers.ModelSerializer):
    tournament_name = serializers.ReadOnlyField(source="tournament.name")
    tournament_start_date = serializers.ReadOnlyField(
        source="tournament.start_date"
    )
    tournament_venue_name = serializers.ReadOnlyField(
        source="tournament.venue.name"
    )
    user_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_code",
            "tournament",
            "tournament_name",
            "tournament_start_date",
            "tournament_venue_name",
            "user_username",
            "status",
            "purchased_at",
        ]
        read_only_fields = [
            "id",
            "ticket_code",
            "status",
            "purchased_at",
            "user_username",
        ]

    def validate_tournament(self, tournament):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            qs = Ticket.objects.filter(
                tournament=tournament,
                user=request.user,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Posiadasz już bilet na ten turniej."
                )
        if not tournament.is_active:
            raise serializers.ValidationError(
                "Nie można kupić biletu na nieaktywny turniej."
            )
        return tournament
