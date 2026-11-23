from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Match, OrganizerProfile, Participant, Tag, Ticket, Tournament, Venue


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


class TournamentViewSetAPITests(TestCase):
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
        self.second_tag = Tag.objects.create(name="Double Out", slug="double-out")
        self.list_url = reverse("tournaments:tournament-list")
        self.api.force_authenticate(user=self.organizer)

    def _valid_payload(self, **overrides):
        payload = {
            "name": "Miejski Turniej Darta",
            "slug": "miejski-turniej-darta",
            "venue": self.venue.id,
            "tag_ids": [self.tag.id],
            "description": (
                "Turniej 501 dla amatorów i półprofesjonalistów w Olsztynie "
                "z pulą nagród oraz transmisją na żywo."
            ),
            "start_date": (timezone.now() + timedelta(days=14)).isoformat(),
            "max_participants": 16,
            "entry_fee": "0.00",
            "is_online": False,
            "is_active": True,
        }
        payload.update(overrides)
        return payload

    def test_api_root_exposes_router_resources(self):
        response = self.api.get("/api/v1/")

        self.assertEqual(response.status_code, 200)
        for resource in (
            "venues",
            "tags",
            "tournaments",
            "participants",
            "matches",
            "tickets",
        ):
            self.assertIn(resource, response.data)

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

    def test_list_uses_lightweight_serializer_and_detail_uses_full_serializer(self):
        create_response = self.api.post(
            self.list_url,
            self._valid_payload(),
            format="json",
        )
        tournament_id = create_response.data["id"]

        list_response = self.api.get(self.list_url)
        self.assertEqual(list_response.status_code, 200)
        list_item = list_response.data[0]
        self.assertIn("short_description", list_item)
        self.assertTrue(list_item["short_description"].endswith("..."))
        self.assertEqual(list_item["tags_count"], 1)
        self.assertNotIn("description", list_item)
        self.assertNotIn("tags_details", list_item)

        detail_url = reverse("tournaments:tournament-detail", args=[tournament_id])
        detail_response = self.api.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("description", detail_response.data)
        self.assertIn("tags_details", detail_response.data)
        self.assertIn("days_until_start", detail_response.data)

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
            "tournaments:tournament-detail",
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
        self.assertFalse(
            Tournament.objects.filter(pk=create_response.data["id"]).exists()
        )

    def test_tournament_custom_actions(self):
        upcoming = Tournament.objects.create(
            name="Przyszły Darmowy",
            slug="przyszly-darmowy",
            organizer=self.organizer,
            venue=self.venue,
            description="Darmowy turniej 501 zaplanowany na kolejny tydzień.",
            start_date=timezone.now() + timedelta(days=10),
            max_participants=16,
            entry_fee="0.00",
            is_active=True,
        )
        upcoming.tags.add(self.tag)

        Tournament.objects.create(
            name="Przeszły Płatny",
            slug="przeszly-platny",
            organizer=self.organizer,
            venue=self.venue,
            description="Turniej historyczny z wpisowym 50 PLN.",
            start_date=timezone.now() - timedelta(days=5),
            max_participants=16,
            entry_fee="50.00",
            is_active=True,
        )

        # detail=False: upcoming
        upcoming_resp = self.api.get(reverse("tournaments:tournament-upcoming"))
        self.assertEqual(upcoming_resp.status_code, 200)
        self.assertEqual(len(upcoming_resp.data), 1)
        self.assertEqual(upcoming_resp.data[0]["id"], upcoming.id)
        self.assertIn("short_description", upcoming_resp.data[0])

        # detail=False: free
        free_resp = self.api.get(reverse("tournaments:tournament-free-tournaments"))
        self.assertEqual(free_resp.status_code, 200)
        self.assertEqual(len(free_resp.data), 1)
        self.assertEqual(free_resp.data[0]["id"], upcoming.id)

        # detail=True: toggle-active
        toggle_url = reverse("tournaments:tournament-toggle-active", args=[upcoming.id])
        toggle_resp = self.api.post(toggle_url)
        self.assertEqual(toggle_resp.status_code, 200)
        self.assertFalse(toggle_resp.data["is_active"])
        upcoming.refresh_from_db()
        self.assertFalse(upcoming.is_active)

        # detail=True: manage-tags (missing tag_id -> 400, POST -> add, DELETE -> remove)
        manage_url = reverse("tournaments:tournament-manage-tags", args=[upcoming.id])
        bad_resp = self.api.post(manage_url, {}, format="json")
        self.assertEqual(bad_resp.status_code, 400)

        add_resp = self.api.post(
            manage_url,
            {"tag_id": self.second_tag.id},
            format="json",
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertEqual(len(add_resp.data), 2)

        rem_resp = self.api.delete(
            manage_url,
            {"tag_id": self.second_tag.id},
            format="json",
        )
        self.assertEqual(rem_resp.status_code, 200)
        self.assertEqual(len(rem_resp.data), 1)

        # detail=True: duplicate
        dup_url = reverse("tournaments:tournament-duplicate", args=[upcoming.id])
        dup_resp = self.api.post(dup_url)
        self.assertEqual(dup_resp.status_code, 201)
        self.assertEqual(dup_resp.data["name"], "Przyszły Darmowy (Kopia)")
        self.assertFalse(dup_resp.data["is_active"])
        self.assertEqual(len(dup_resp.data["tags_details"]), 1)

    def test_venue_destroy_blocked_when_tournaments_exist_and_tag_tournaments_action(self):
        tournament = Tournament.objects.create(
            name="Puchar Olsztyna",
            slug="puchar-olsztyna",
            organizer=self.organizer,
            venue=self.venue,
            description="Turniej pucharowy 501 w obiekcie Dart Arena.",
            start_date=timezone.now() + timedelta(days=7),
            max_participants=16,
            is_active=True,
        )
        tournament.tags.add(self.tag)

        venue_detail = reverse("tournaments:venue-detail", args=[self.venue.id])
        del_resp = self.api.delete(venue_detail)
        self.assertEqual(del_resp.status_code, 400)
        self.assertIn("error", del_resp.data)

        venue_tournaments = reverse("tournaments:venue-tournaments", args=[self.venue.id])
        vt_resp = self.api.get(venue_tournaments)
        self.assertEqual(vt_resp.status_code, 200)
        self.assertEqual(len(vt_resp.data), 1)

        tag_tournaments = reverse("tournaments:tag-tournaments", args=[self.tag.id])
        tt_resp = self.api.get(tag_tournaments)
        self.assertEqual(tt_resp.status_code, 200)
        self.assertEqual(len(tt_resp.data), 1)

    def test_cbv_and_summary_endpoints(self):
        Tournament.objects.create(
            name="Płatny Turniej",
            slug="platny-turniej",
            organizer=self.organizer,
            venue=self.venue,
            description="Turniej płatny z nagrodami dla najlepszych graczy.",
            start_date=timezone.now() + timedelta(days=4),
            max_participants=16,
            entry_fee="40.00",
            is_active=True,
        )

        apiview_resp = self.api.get(reverse("tournaments:apiview-tournament-list"))
        self.assertEqual(apiview_resp.status_code, 200)
        self.assertEqual(len(apiview_resp.data), 1)

        generic_resp = self.api.get(reverse("tournaments:generic-tournament-list"))
        self.assertEqual(generic_resp.status_code, 200)
        self.assertIn("short_description", generic_resp.data[0])

        summary_resp = self.api.get(reverse("tournaments:platform-summary"))
        self.assertEqual(summary_resp.status_code, 200)
        self.assertEqual(summary_resp.data["total_tournaments"], 1)
        self.assertEqual(summary_resp.data["active_tournaments"], 1)
        self.assertEqual(summary_resp.data["upcoming_tournaments"], 1)
        self.assertEqual(summary_resp.data["venues_count"], 1)
        self.assertEqual(summary_resp.data["tags_count"], 2)
        self.assertEqual(summary_resp.data["average_entry_fee"], 40.0)


class MatchViewSetAPITests(TestCase):
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
        self.list_url = reverse("tournaments:match-list")
        self.api.force_authenticate(user=self.organizer)

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
            "tournaments:match-detail",
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

    def test_live_and_finish_actions(self):
        dart_match = Match.objects.create(
            tournament=self.tournament,
            player_home=self.player_home,
            player_away=self.player_away,
            scheduled_at=timezone.now(),
            legs_to_win=3,
            status=Match.Status.IN_PROGRESS,
        )

        live_resp = self.api.get(reverse("tournaments:match-live"))
        self.assertEqual(live_resp.status_code, 200)
        self.assertEqual(len(live_resp.data), 1)
        self.assertEqual(live_resp.data[0]["id"], dart_match.id)

        finish_url = reverse("tournaments:match-finish", args=[dart_match.id])
        finish_resp = self.api.post(
            finish_url,
            {"home_legs": 3, "away_legs": 2},
            format="json",
        )
        self.assertEqual(finish_resp.status_code, 200)
        self.assertTrue(finish_resp.data["is_finished"])
        self.assertEqual(finish_resp.data["winner"], self.player_home.id)
        self.assertEqual(finish_resp.data["scoreline"], "3:2")

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
        detail_url = reverse("tournaments:match-detail", args=[dart_match.pk])

        response = self.api.delete(detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Match.objects.filter(pk=dart_match.pk).exists())


class JWTAuthAndUserResourcesTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.register_url = reverse("tournaments:api-register")
        self.me_url = reverse("tournaments:api-me")
        self.token_url = reverse("token_obtain_pair")
        self.refresh_url = reverse("token_refresh")
        self.verify_url = reverse("token_verify")
        self.tournaments_url = reverse("tournaments:tournament-list")
        self.tickets_url = reverse("tournaments:ticket-list")
        self.venue = Venue.objects.create(
            name="Dart Hall",
            city="Olsztyn",
            capacity=64,
        )

    def _register_and_login(self, username, email, company_name="Dart Club"):
        reg_resp = self.api.post(
            self.register_url,
            {
                "username": username,
                "email": email,
                "first_name": "Jan",
                "last_name": "Kowalski",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "company_name": company_name,
            },
            format="json",
        )
        self.assertEqual(reg_resp.status_code, 201)

        token_resp = self.api.post(
            self.token_url,
            {"username": username, "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(token_resp.status_code, 200)
        return token_resp.data

    def test_registration_creates_user_and_organizer_profile(self):
        tokens = self._register_and_login("dart_org", "org@example.com", "Olsztyn Darts")
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)

        user = get_user_model().objects.get(username="dart_org")
        self.assertTrue(OrganizerProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.company_name, "Olsztyn Darts")

        verify_resp = self.api.post(
            self.verify_url,
            {"token": tokens["access"]},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, 200)

        refresh_resp = self.api.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, 200)
        self.assertIn("access", refresh_resp.data)

    def test_registration_validates_password_match_and_unique_email(self):
        mismatch_resp = self.api.post(
            self.register_url,
            {
                "username": "bad_user",
                "email": "bad@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "DifferentPassword123!",
            },
            format="json",
        )
        self.assertEqual(mismatch_resp.status_code, 400)
        self.assertIn("password_confirm", mismatch_resp.data)

        self._register_and_login("first_user", "dup@example.com")
        dup_resp = self.api.post(
            self.register_url,
            {
                "username": "second_user",
                "email": "DUP@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
            },
            format="json",
        )
        self.assertEqual(dup_resp.status_code, 400)
        self.assertIn("email", dup_resp.data)

    def test_jwt_create_tournament_assigns_organizer_from_token(self):
        payload = {
            "name": "Turniej JWT Open",
            "slug": "turniej-jwt-open",
            "venue": self.venue.id,
            "description": "Turniej 501 tworzony przez użytkownika uwierzytelnionego tokenem JWT.",
            "start_date": (timezone.now() + timedelta(days=10)).isoformat(),
            "max_participants": 16,
            "entry_fee": "20.00",
            "is_online": False,
            "is_active": True,
        }

        anon_resp = self.api.post(self.tournaments_url, payload, format="json")
        self.assertEqual(anon_resp.status_code, 401)

        tokens = self._register_and_login("jwt_creator", "creator@example.com")
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        create_resp = self.api.post(self.tournaments_url, payload, format="json")
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(create_resp.data["organizer_username"], "jwt_creator")

    def test_current_user_me_endpoint_read_and_update(self):
        anon_resp = self.api.get(self.me_url)
        self.assertEqual(anon_resp.status_code, 401)

        tokens = self._register_and_login("profile_user", "me@example.com", "Stary Klub")
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        get_resp = self.api.get(self.me_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.data["username"], "profile_user")
        self.assertEqual(get_resp.data["profile"]["company_name"], "Stary Klub")
        self.assertFalse(get_resp.data["profile"]["is_verified"])

        patch_resp = self.api.patch(
            self.me_url,
            {
                "first_name": "Kacper",
                "profile": {
                    "company_name": "Nowy Klub Darta",
                    "bio": "Organizator ligi 501 w Olsztynie.",
                    "website": "https://dart.example.com",
                    "is_verified": True,
                },
            },
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.data["first_name"], "Kacper")
        self.assertEqual(patch_resp.data["profile"]["company_name"], "Nowy Klub Darta")
        self.assertEqual(
            patch_resp.data["profile"]["bio"],
            "Organizator ligi 501 w Olsztynie.",
        )
        self.assertFalse(patch_resp.data["profile"]["is_verified"])

    def test_ticket_purchase_validation_and_user_isolation(self):
        tokens_a = self._register_and_login("player_a", "a@example.com")
        tokens_b = self._register_and_login("player_b", "b@example.com")
        owner = get_user_model().objects.get(username="player_a")

        active_tournament = Tournament.objects.create(
            name="Puchar Darta",
            slug="puchar-darta",
            organizer=owner,
            venue=self.venue,
            description="Aktywny turniej pucharowy 501 z biletami UUID.",
            start_date=timezone.now() + timedelta(days=5),
            max_participants=16,
            is_active=True,
        )
        inactive_tournament = Tournament.objects.create(
            name="Szkic Turnieju",
            slug="szkic-turnieju",
            organizer=owner,
            venue=self.venue,
            description="Nieaktywny szkic turnieju — brak sprzedaży biletów.",
            start_date=timezone.now() + timedelta(days=8),
            max_participants=16,
            is_active=False,
        )

        # Anonimowy użytkownik nie ma dostępu do biletów
        self.api.credentials()
        self.assertEqual(self.api.get(self.tickets_url).status_code, 401)

        # Gracz A kupuje bilet
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_a['access']}")
        buy_resp = self.api.post(
            self.tickets_url,
            {"tournament": active_tournament.id},
            format="json",
        )
        self.assertEqual(buy_resp.status_code, 201)
        self.assertEqual(buy_resp.data["user_username"], "player_a")
        self.assertTrue(buy_resp.data["ticket_code"])
        ticket_id = buy_resp.data["id"]

        # Drugi bilet na ten sam turniej jest blokowany
        dup_resp = self.api.post(
            self.tickets_url,
            {"tournament": active_tournament.id},
            format="json",
        )
        self.assertEqual(dup_resp.status_code, 400)
        self.assertIn("tournament", dup_resp.data)

        # Bilet na nieaktywny turniej jest blokowany
        inactive_resp = self.api.post(
            self.tickets_url,
            {"tournament": inactive_tournament.id},
            format="json",
        )
        self.assertEqual(inactive_resp.status_code, 400)
        self.assertIn("tournament", inactive_resp.data)

        # Gracz B widzi pustą listę i nie ma dostępu do biletu gracza A (izolacja)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_b['access']}")
        list_b = self.api.get(self.tickets_url)
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(len(list_b.data), 0)

        detail_b = self.api.get(
            reverse("tournaments:ticket-detail", args=[ticket_id])
        )
        self.assertEqual(detail_b.status_code, 404)
        self.assertEqual(Ticket.objects.count(), 1)
