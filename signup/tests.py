import datetime
import re
from copy import deepcopy

import pytest
from django.core import signing
from django.urls import reverse

from signup import services, views
from signup.services import (
    PROP_CONFIRMED,
    PROP_REMINDED,
    PROP_REQUESTED,
    make_token,
    process_pending,
)

PENDING = 100
CONFIRMED = 200
OTHER = 300
TODAY = datetime.date(2026, 11, 2)


class FakeWeblingAPI:
    def __init__(self, members: dict[int, dict]):
        self.members = members

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def fetch_members_by_group_id(self, group_id):
        return {
            member_id: deepcopy(member)
            for member_id, member in self.members.items()
            if group_id in member["parents"]
        }

    def fetch_member(self, member_id):
        return deepcopy(self.members.get(member_id))

    def update_member(self, member_id, properties, parents=None):
        self.members[member_id]["properties"].update(properties)
        if parents:
            self.members[member_id]["parents"] = parents

    def delete_member(self, member_id):
        del self.members[member_id]


def make_member(member_id, email="ada@example.org", parents=(PENDING,), **properties):
    return {
        "id": member_id,
        "parents": list(parents),
        "properties": {"Vorname": "Ada", "Name": "Lovelace", "E-Mail": email, **properties},
    }


@pytest.fixture(autouse=True)
def signup_settings(settings):
    settings.SIGNUP_PENDING_GROUP_ID = PENDING
    settings.SIGNUP_CONFIRMED_GROUP_ID = CONFIRMED
    settings.SIGNUP_BASE_URL = "https://portal.example.org/"
    settings.SIGNUP_NOTIFY_EMAILS = ["vorstand@example.org"]
    settings.SIGNUP_REMINDER_DAYS = 3
    settings.SIGNUP_EXPIRY_DAYS = 14
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def api(monkeypatch):
    api = FakeWeblingAPI({})
    monkeypatch.setattr(views, "WeblingAPI", lambda api_key: api)
    return api


def days_ago(days):
    return (TODAY - datetime.timedelta(days=days)).isoformat()


def test_process_pending_requests_confirmation(mailoutbox):
    api = FakeWeblingAPI({1: make_member(1)})

    stats = process_pending(api, today=TODAY)

    assert stats["requested"] == 1
    assert api.members[1]["properties"][PROP_REQUESTED] == TODAY.isoformat()
    [mail] = mailoutbox
    assert mail.to == ["ada@example.org"]
    assert "Hallo Ada" in mail.body
    assert "16.11.2026" in mail.body
    assert re.search(r"https://portal\.example\.org/anmeldung/bestaetigen/\S+/", mail.body)


def test_process_pending_ignores_other_groups(mailoutbox):
    api = FakeWeblingAPI({1: make_member(1, parents=[OTHER])})

    process_pending(api, today=TODAY)

    assert mailoutbox == []
    assert PROP_REQUESTED not in api.members[1]["properties"]


@pytest.mark.parametrize(
    "members",
    [
        pytest.param({1: make_member(1, email="kaputt")}, id="invalid-email"),
        pytest.param({1: make_member(1, email="")}, id="missing-email"),
        pytest.param(
            {0: make_member(0, parents=[CONFIRMED]), 1: make_member(1)}, id="already-confirmed"
        ),
    ],
)
def test_process_pending_skips_without_mail(mailoutbox, members):
    api = FakeWeblingAPI(members)

    stats = process_pending(api, today=TODAY)

    assert stats == dict(requested=0, reminded=0, deleted=0, skipped=1)
    assert mailoutbox == []
    # Still marked so it expires
    assert api.members[1]["properties"][PROP_REQUESTED] == TODAY.isoformat()


def test_process_pending_mails_duplicate_address_once(mailoutbox):
    api = FakeWeblingAPI({1: make_member(1), 2: make_member(2, email="ADA@example.org ")})

    stats = process_pending(api, today=TODAY)

    assert stats["requested"] == 1
    assert stats["skipped"] == 1
    [mail] = mailoutbox
    assert make_token(1, "ada@example.org") in mail.body


def test_process_pending_reminds_once(mailoutbox):
    api = FakeWeblingAPI({1: make_member(1, **{PROP_REQUESTED: days_ago(3)})})

    assert process_pending(api, today=TODAY)["reminded"] == 1
    assert process_pending(api, today=TODAY)["reminded"] == 0

    [mail] = mailoutbox
    assert mail.subject.startswith("Erinnerung")
    assert "13.11.2026" in mail.body
    assert api.members[1]["properties"][PROP_REMINDED] == TODAY.isoformat()


def test_process_pending_waits_before_reminder(mailoutbox):
    api = FakeWeblingAPI({1: make_member(1, **{PROP_REQUESTED: days_ago(2)})})

    assert process_pending(api, today=TODAY) == dict(requested=0, reminded=0, deleted=0, skipped=0)
    assert mailoutbox == []


def test_process_pending_deletes_expired(mailoutbox):
    api = FakeWeblingAPI(
        {
            1: make_member(1, **{PROP_REQUESTED: days_ago(14), PROP_REMINDED: days_ago(11)}),
            2: make_member(2, email="bob@example.org", **{PROP_REQUESTED: days_ago(13)}),
        }
    )

    stats = process_pending(api, today=TODAY)

    assert stats["deleted"] == 1
    assert list(api.members) == [2]


def test_confirm_flow(client, api, mailoutbox):
    api.members[1] = make_member(1, parents=[PENDING, OTHER], **{PROP_REQUESTED: days_ago(1)})
    url = reverse("signup:confirm", args=[make_token(1, "ada@example.org")])

    response = client.get(url)
    assert response.status_code == 200
    assert response.context["state"] == "confirm"
    # GET alone must not confirm (mail scanners open links)
    assert api.members[1]["parents"] == [PENDING, OTHER]

    response = client.post(url, follow=True)
    assert response.status_code == 200
    assert response.context["state"] == "done"
    assert api.members[1]["parents"] == [OTHER, CONFIRMED]
    assert api.members[1]["properties"][PROP_CONFIRMED]
    [mail] = mailoutbox
    assert mail.to == ["vorstand@example.org"]
    assert "Ada Lovelace" in mail.subject
    assert "E-Mail: ada@example.org" in mail.body

    # Opening the link again just shows the success page
    response = client.post(url)
    assert response.status_code == 200
    assert response.context["state"] == "done"
    assert len(mailoutbox) == 1


def test_confirm_without_notify_emails(client, api, mailoutbox, settings):
    settings.SIGNUP_NOTIFY_EMAILS = []
    api.members[1] = make_member(1)

    client.post(reverse("signup:confirm", args=[make_token(1, "ada@example.org")]))

    assert CONFIRMED in api.members[1]["parents"]
    assert mailoutbox == []


@pytest.mark.parametrize(
    "member, email, status",
    [
        pytest.param(None, "ada@example.org", 410, id="deleted"),
        pytest.param(make_member(1), "eve@example.org", 410, id="email-changed"),
        pytest.param(make_member(1, parents=[OTHER]), "ada@example.org", 410, id="moved"),
    ],
)
def test_confirm_rejects(client, api, member, email, status):
    if member:
        api.members[1] = member

    response = client.post(reverse("signup:confirm", args=[make_token(1, email)]))

    assert response.status_code == status
    assert response.context["state"] == "expired"
    if member:
        assert CONFIRMED not in api.members[1]["parents"]


def test_confirm_invalid_token(client, api):
    api.members[1] = make_member(1)
    token = make_token(1, "ada@example.org")

    response = client.post(reverse("signup:confirm", args=[token[:-2] + "xx"]))

    assert response.status_code == 404
    assert response.context["state"] == "invalid"
    assert CONFIRMED not in api.members[1]["parents"]


def test_confirm_expired_token(client, api, monkeypatch):
    api.members[1] = make_member(1)
    token = make_token(1, "ada@example.org")

    def expired(*args, **kwargs):
        raise signing.SignatureExpired()

    monkeypatch.setattr(services.signing, "loads", expired)
    response = client.get(reverse("signup:confirm", args=[token]))

    assert response.status_code == 410
    assert response.context["state"] == "expired"
