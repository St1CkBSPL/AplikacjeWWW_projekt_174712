from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Tournament


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
