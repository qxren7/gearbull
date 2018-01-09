"""
django app's urls.
"""
from django.conf.urls import include
from django.conf.urls import url

from fuxi_framework import views

urlpatterns=[
    url(r'^index/$', views.index, name="index"),
    url(r'^jobs/$', views.show_jobs, name="show_jobs"),
    url(r'^tasks/$', views.show_tasks, name="show_tasks"),
    url(r'^actions/$', views.show_actions, name="show_actions"),
    url(r'^auth/username$', views.get_username, name="username"),
    url(r'v1/jobs/', views.jobs),
    url(r'v1/jobs/(?P<job_id>.+)/$', views.jobs),
    url(r'v1/tasks/', views.tasks),
    url(r'v1/tasks/(?P<task_id>.+)/$', views.tasks),
    url(r'v1/actions/', views.actions),
    url(r'v1/actions/(?P<action_id>.+)/$', views.actions),
    url(r'v1/control/', views.control),
    #url(r'v1/control/(?P<range>.*)/$', views.control)
    url(r'^$', views.index, name="index"),
]
