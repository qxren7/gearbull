"""fuxi URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin

from django.contrib.auth.models import User
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers, serializers, viewsets
from django.views.generic import TemplateView 
from django_cas import views as cas_views
import auto_scale


router = routers.DefaultRouter()

urlpatterns = [
    url(r'^demo/', include('demo.urls')),
    url(r'^accounts/login/$', cas_views.login),
    url(r'^accounts/logout/$', cas_views.logout),
    url(r'^zhongjing/', include('zhongjing.urls')),
    url(r'^framework/', include('fuxi_framework.urls')),
    url(r'^api/framework/', include('fuxi_framework.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^accelerator/', include('accelerator.urls')),
    url(r'^api/accelerator/', include('accelerator.urls')),
    url(r'^auto_scale/', include('auto_scale.urls')),
    url(r'^auto_switch/', include('auto_switch.urls')),
    url(r'^api/auto_scale/', include('auto_scale.urls')),
    url(r'^dt/', include('dt_platform.urls')),
    url(r'^api/dt/', include('dt_platform.urls')),
    url(r'^$', TemplateView.as_view(template_name="index.html")),
    url(r'^api/zhongjing/', include('zhongjing.urls')),
    url(r'^tera/', include('tera_platform.urls')),
    url(r'^ins_consis/', include('ins_consistency.urls')),
    url(r'^api/core_server/', include('core_server.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
