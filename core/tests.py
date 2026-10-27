import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_index_lists_modules(client):
    response = client.get(reverse("core:index"))
    assert response.status_code == 200
    assert reverse("voting:index") in response.content.decode()


@pytest.mark.parametrize(
    "old_path, new_path",
    [
        ("/create/", "/bieterrunde/create/"),
        (
            "/manage/0b0e4a5c-8c1f-4b4e-9c2a-1d2f3e4a5b6c",
            "/bieterrunde/manage/0b0e4a5c-8c1f-4b4e-9c2a-1d2f3e4a5b6c",
        ),
        ("/registration/x/1/token/?a=b", "/bieterrunde/registration/x/1/token/?a=b"),
    ],
)
def test_legacy_voting_urls_redirect(client, old_path, new_path):
    response = client.get(old_path)
    assert response.status_code == 301
    assert response["Location"] == new_path
