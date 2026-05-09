from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path('', views.SmartLoginView.as_view(), name='login'),
    path('sair/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('cadastre-se/', views.signup, name='signup'),
    path('cadastro/finalizado/', views.signup_success, name='signup_success'),
    path('minha-inscricao/', views.volunteer_dashboard, name='volunteer_dashboard'),
    path('minha-inscricao/documentacao/', views.volunteer_documentation_dashboard, name='volunteer_documentation_dashboard'),
    path('minha-inscricao/financeiro/', views.volunteer_financial_dashboard, name='volunteer_financial_dashboard'),
    path('pagamento/<int:payment_id>/comprovante/', views.volunteer_payment_upload, name='volunteer_payment_upload'),
    path('missionario/<int:volunteer_id>/ficha/', views.volunteer_registration_pdf, name='volunteer_registration_pdf'),
    path('missionario/<int:volunteer_id>/documentacao/', views.volunteer_documentation_upload, name='volunteer_documentation_upload'),
    path('painel/', views.admin_dashboard, name='admin_dashboard'),
    path('painel/financeiro/', views.financial_dashboard, name='financial_dashboard'),
    path('painel/permissoes/', views.permissions_dashboard, name='permissions_dashboard'),
]
