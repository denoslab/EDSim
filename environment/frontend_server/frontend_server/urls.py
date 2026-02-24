"""frontend_server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from translator import views as translator_views

urlpatterns = [
    url(r'^$', translator_views.landing, name='landing'),
    url(r'^simulator_home$', translator_views.home, name='home'),
    url(r'^demo/(?P<sim_code>[\w-]+)/(?P<step>[\w-]+)/(?P<play_speed>[\w-]+)/$', translator_views.demo, name='demo'),
    url(r'^replay/(?P<sim_code>[\w-]+)/(?P<step>[\w-]+)/$', translator_views.replay, name='replay'),
    url(r'^replay_persona_state/(?P<sim_code>[\w-]+)/(?P<step>[\w-]+)/(?P<persona_name>[\w-]+)/$', translator_views.replay_persona_state, name='replay_persona_state'),
    url(r'^process_environment/$', translator_views.process_environment, name='process_environment'),
    url(r'^update_environment/$', translator_views.update_environment, name='update_environment'),
    url(r'^path_tester/$', translator_views.path_tester, name='path_tester'),
    url(r'^path_tester_update/$', translator_views.path_tester_update, name='path_tester_update'),
    url(r'^get_maze_visuals/(?P<sim_code>[\w-]+)/(?P<mode>[\w-]+)/$', translator_views.get_maze_visuals, name='get_maze_visuals'),
    url(r'^start_simulation/$', translator_views.start_page, name='start_page'),
    url(r'^start_backend/(?P<origin>[\w-]+)/(?P<target>[\w-]+)/$', translator_views.start_backend, name='start_backend'),
    url(r'^save_simulation_settings/$', translator_views.save_simulation_settings, name='save_simulation_settings'),
    url(r'^send_sim_command/$', translator_views.send_sim_command, name='send_sim_command'),
    url(r'^get_sim_output/$', translator_views.get_sim_output, name='get_sim_output'),
    url(r'^force_shutdown/$', translator_views.force_shutdown, name='force_shutdown'),
    url(r'^data_visualization$', translator_views.data_page, name = 'data_page'),
    url(r'^live_dashboard$', translator_views.live_dashboard_page, name='live_dashboard_page'),
    url(r'^api/live_dashboard/$', translator_views.live_dashboard_api, name='live_dashboard_api'),
    url(r'^api/state_times/$', translator_views.data_api, name='data_api'),
    url('character_image', translator_views.get_image_png, name='get_image_png'),
    path('admin/', admin.site.urls),
]
