from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/market-summary/', views.market_summary, name='market_summary'),
    path('api/stock-suggestions/', views.stock_suggestions, name='stock_suggestions'),
    path('quote/<str:symbol>/', views.stock_quote, name='stock_quote'),
]
