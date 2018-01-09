"""
django app's urls.
"""
from django.conf.urls import include
from django.conf.urls import url

from zhongjing import views

urlpatterns=[
        url(r'^$', views.dashboard, name="dashboard"),
        url(r'^host/operate/(?P<task_type>\w+)/$', views.host_operate, name="host_operate"),
        url(r'^host/operate/$', views.host_operate, name="host_operate"),
        url(r'^repair/$', views.repair, name="repair"),
        url(r'^operates/$', views.operates, name="operates"),
        url(r'^failures/$', views.failures, name="failures"),
        url(r'^consistent/$', views.consistent, name="consistent"),
        url(r'^repair/alading/host/$', views.repair_alading_host, name="repair_alading_host"),
        url(r'^reinstall/alading/host/$', views.reinstall_alading_host, 
            name="reinstall_alading_host"),
        url(r'^reinstall/galaxy/host/$', views.reinstall_galaxy_host, 
            name="reinstall_galaxy_host"),
        url(r'^reinstall/$', views.reinstall, name="reinstall"),
        url(r'^freeze_beehive_host/$', views.freeze_beehive_host, name="freeze_beehive_host"),
        url(r'^deploy_agent/$', views.deploy_agent, name="deploy_agent"),
        url(r'^host/detail/$', views.host_detail, name="host_detail"),
        url(r'^dashboard/$', views.dashboard, name="dashboard"),
        url(r'^service/(?P<service_name>\w+)/$', views.service, name="service"),
        url(r'^trigger/(?P<task>\w+)/$', views.trigger_tasks, name="trigger_tasks"),
        url(r'^push/stat/(?P<stat_type>\w+)/$', views.push_stat_data, name="push_stat_data"),


        #
        url(r'^index/$', views.index, name="index"),
        url(r'^jobs/$', views.jobs, name="jobs"),
        url(r'^query/(?P<target>\w+)/$', views.query, name='query'), 
        url(r'^query/(?P<target>\w+)/(?P<params>[\w.-]+)/$', 
            views.query_by_filter, name='query_by_filter'), 

        # for dev
        url(r'^fake_operate/$', views.fake_operate, name="fake_operate"),
        url(r'^dev/index/$', views.dev_index, name="dev_index"),
        url(r'^demo/$', views.demo, name="demo"),
]
