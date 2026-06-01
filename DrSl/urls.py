"""
Главный файл маршрутизации проекта DrSl.
...
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse_lazy  # ✅ Новый импорт


# ✅ Кастомный вход: всегда редиректит на дашборд
class CustomLoginView(LoginView):
    def get_success_url(self):
        # 1. Проверяем, с какой страницы пришёл пользователь
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        # 2. Если нет → стандартный редирект на дашборд
        return reverse_lazy('vault:dashboard')


# =========================================================
# ГЛАВНАЯ СТРАНИЦА
# =========================================================

def root_page(request):
    if request.user.is_authenticated:
        return redirect('vault:dashboard')

    return CustomLoginView.as_view(  # ✅ Используем наш класс
        template_name='registration/login.html'
    )(request)


# =========================================================
# ВЫХОД ИЗ СИСТЕМЫ
# =========================================================

def custom_logout(request):
    logout(request)
    return redirect('home')


# =========================================================
# URL МАРШРУТЫ ПРОЕКТА
# =========================================================

urlpatterns = [
    path('', root_page, name='home'),
    path('logout/', custom_logout, name='logout'),
    path('admin/', admin.site.urls),
    path('vault/', include('vault.urls')),
    path('groups/', include('groups.urls')),
    path('students/', include('students.urls')),
    path('reports/', include('reports.urls')),
    path('classrooms/', include('classrooms.urls')),
    path('teachers/', include('teachers.urls')),
    path('masters/', include('masters.urls')),
]