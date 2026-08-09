from django.urls import include, path
from django.contrib import admin
from commerce.api import api

urlpatterns = [path('admin/', admin.site.urls), path('api/', include(api.urls))]
