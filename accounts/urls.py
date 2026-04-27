from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('cadastre-se/', views.signup, name='signup'),
    path('cadastro/finalizado/', views.signup_success, name='signup_success'),
    path('painel/', views.admin_dashboard, name='admin_dashboard'),
    path('painel/financeiro/', views.financial_dashboard, name='financial_dashboard'),
]
