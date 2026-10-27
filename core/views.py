from django.shortcuts import render
from django.urls import reverse


def index(request):
    modules = [
        {
            "name": "Bieterrunde",
            "description": "Solidarische Festlegung der Mitgliedsbeiträge",
            "url": reverse("voting:index"),
            "icon": "bx-coin-stack",
        },
    ]
    return render(request, "core/index.html", dict(modules=modules))
