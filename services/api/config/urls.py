from django.urls import include, path

urlpatterns = [
    path("api/transactional/", include("transactional.urls")),
]
