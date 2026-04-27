from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path('', views.SmartLoginView.as_view(), name='login'),
    path('sair/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('cadastre-se/', views.signup, name='signup'),
    path('cadastro/finalizado/', views.signup_success, name='signup_success'),
    path('painel/', views.admin_dashboard, name='admin_dashboard'),
    path('painel/financeiro/', views.financial_dashboard, name='financial_dashboard'),
]
