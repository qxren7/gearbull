from django.conf.urls import url
from django.urls import path
from django.conf.urls import include

from . import views

from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"jobs", views.JobViewSet)
router.register(r"tasks", views.TaskViewSet)
router.register(r"actions", views.ActionViewSet)
router.register(r"users", views.UserViewSet)

urlpatterns = [
    # RESTFUL API
    path("", include(router.urls)),
    url(r"^api/(?P<task>\w+)/$", views.api, name="api"),
]
