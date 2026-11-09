from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Match, Participant, Tag, Tournament, Venue


class TournamentListViewTests(TestCase):
    def test_list_page_renders_tournaments_from_database(self):
        organizer = get_user_model().objects.create_user(
            username="organizer",
            password="test-password",
        )
        Tournament.objects.create(
            name="Jesienny Turniej Darta",
            slug="jesienny-turniej-darta",
            organizer=organizer,
            start_date=timezone.now() + timedelta(days=7),
            max_participants=16,
        )

        response = self.client.get(reverse("tournaments:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "tournaments/tournament_list.html")
        self.assertContains(response, "Jesienny Turniej Darta")
        self.assertContains(response, "0 / 16")

    def test_list_page_displays_empty_state(self):
        response = self.client.get(reverse("tournaments:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nie dodano jeszcze żadnych turniejów.")


class TournamentAPITests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.organizer = get_user_model().objects.create_user(
            username="organizer",
            password="test-password",
        )
        self.venue = Venue.objects.create(
            name="Dart Arena",
            city="Olsztyn",
            address="ul. Sportowa 1",
            capacity=32,
        )
        self.tag = Tag.objects.create(name="501", slug="501")
        self.list_url = reverse("tournaments:api-tournament-list-create")

    def _valid_payload(self, **overrides):
        payload = {
            "name": "Miejski Turniej Darta",
            "slug": "miejski-turniej-darta",
            "organizer": self.organizer.id,
            "venue": self.venue.id,
            "tag_ids": [self.tag.id],
            "description": "Turniej 501 dla amatorów i półprofesjonalistów.",
            "start_date": (timezone.now() + timedelta(days=14)).isoformat(),
            "max_participants": 16,
            "entry_fee": "0.00",
            "is_online": False,
            "is_active": True,
        }
        payload.update(overrides)
        return payload

    def test_create_tournament_returns_nested_tags_and_computed_fields(self):
        response = self.api.post(self.list_url, self._valid_payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Miejski Turniej Darta")
        self.assertEqual(response.data["organizer_username"], "organizer")
        self.assertEqual(response.data["venue_name"], "Dart Arena")
        self.assertEqual(response.data["tags_details"][0]["slug"], "501")
        self.assertTrue(response.data["is_free"])
        self.assertGreaterEqual(response.data["days_until_start"], 13)
        self.assertEqual(response.data["seats_left"], 16)

    def test_list_uses_select_related_and_prefetch(self):
        tournament = Tournament.objects.create(
            name="Turniej testowy",
            slug="turniej-testowy",
            organizer=self.organizer,
            venue=self.venue,
            description="Opis turnieju testowego darta 501.",
            start_date=timezone.now() + timedelta(days=5),
            max_participants=8,
        )
        tournament.tags.add(self.tag)

        with CaptureQueriesContext(connection) as ctx:
            response = self.api.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        sql = " ".join(query["sql"] for query in ctx.captured_queries)
        self.assertIn("JOIN", sql.upper())
        self.assertLessEqual(len(ctx.captured_queries), 5)

    def test_rejects_past_start_date(self):
        payload = self._valid_payload(
            start_date=(timezone.now() - timedelta(days=1)).isoformat(),
        )
        response = self.api.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("start_date", response.data)

    def test_rejects_odd_max_participants(self):
        response = self.api.post(
            self.list_url,
            self._valid_payload(max_participants=15),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("max_participants", response.data)

    def test_rejects_paid_tournament_with_free_in_name(self):
        response = self.api.post(
            self.list_url,
            self._valid_payload(
                name="Darmowy Open Darta",
                slug="darmowy-open-darta",
                entry_fee="25.00",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("entry_fee", response.data)

    def test_rejects_offline_tournament_without_venue(self):
        payload = self._valid_payload(venue=None)
        response = self.api.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("venue", response.data)

    def test_patch_and_delete_tournament(self):
        create_response = self.api.post(
            self.list_url,
            self._valid_payload(),
            format="json",
        )
        detail_url = reverse(
            "tournaments:api-tournament-detail",
            args=[create_response.data["id"]],
        )

        patch_response = self.api.patch(
            detail_url,
            {"max_participants": 32},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["max_participants"], 32)

        delete_response = self.api.delete(detail_url)
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Tournament.objects.filter(pk=create_response.data["id"]).exists())


class MatchAPITests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.organizer = get_user_model().objects.create_user(
            username="organizer",
            password="test-password",
        )
        player_one_user = get_user_model().objects.create_user(
            username="player-one",
            password="test-password",
        )
        player_two_user = get_user_model().objects.create_user(
            username="player-two",
            password="test-password",
        )
        self.venue = Venue.objects.create(
            name="Bullseye Club",
            city="Olsztyn",
            capacity=40,
        )
        self.tournament = Tournament.objects.create(
            name="Liga Darta",
            slug="liga-darta",
            organizer=self.organizer,
            venue=self.venue,
            description="Cotygodniowa liga 501 na ośmiu osiach.",
            start_date=timezone.now() + timedelta(days=3),
            max_participants=8,
        )
        self.player_home = Participant.objects.create(
            tournament=self.tournament,
            user=player_one_user,
            nickname="The Power",
            seed=1,
        )
        self.player_away = Participant.objects.create(
            tournament=self.tournament,
            user=player_two_user,
            nickname="Barney",
            seed=2,
        )
        self.list_url = reverse("tournaments:api-match-list-create")

    def _valid_payload(self, **overrides):
        payload = {
            "tournament": self.tournament.id,
            "player_home": self.player_home.id,
            "player_away": self.player_away.id,
            "scheduled_at": (timezone.now() + timedelta(days=4)).isoformat(),
            "legs_to_win": 3,
            "home_legs": 0,
            "away_legs": 0,
            "status": Match.Status.SCHEDULED,
        }
        payload.update(overrides)
        return payload

    def test_create_and_patch_match(self):
        response = self.api.post(self.list_url, self._valid_payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["player_home_nickname"], "The Power")
        self.assertEqual(response.data["scoreline"], "0:0")
        self.assertFalse(response.data["is_finished"])

        detail_url = reverse(
            "tournaments:api-match-detail",
            args=[response.data["id"]],
        )
        patch_response = self.api.patch(
            detail_url,
            {
                "status": Match.Status.FINISHED,
                "home_legs": 3,
                "away_legs": 1,
                "winner": self.player_home.id,
            },
            format="json",
        )

        self.assertEqual(patch_response.status_code, 200)
        self.assertTrue(patch_response.data["is_finished"])
        self.assertEqual(patch_response.data["scoreline"], "3:1")
        self.assertEqual(patch_response.data["winner_nickname"], "The Power")

    def test_rejects_same_player_twice(self):
        response = self.api.post(
            self.list_url,
            self._valid_payload(player_away=self.player_home.id),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("player_away", response.data)

    def test_delete_match(self):
        dart_match = Match.objects.create(
            tournament=self.tournament,
            player_home=self.player_home,
            player_away=self.player_away,
            scheduled_at=timezone.now() + timedelta(days=4),
        )
        detail_url = reverse("tournaments:api-match-detail", args=[dart_match.pk])

        response = self.api.delete(detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Match.objects.filter(pk=dart_match.pk).exists())
