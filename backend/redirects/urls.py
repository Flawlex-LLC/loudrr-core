from django.urls import path

from . import views

urlpatterns = [
    path("<str:token>/", views.redirect_view, name="redirect"),
]
