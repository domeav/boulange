from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("recipes", views.recipes, name="recipes"),
    path("actions", views.actions, name="actions"),
]
