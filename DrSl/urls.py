"""
Главный файл маршрутизации проекта DrSl.
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from django.views.decorators.http import require_http_methods

# ❌ УДАЛЕНО: from . import views  (этого файла нет, он вызывал ошибку)


# =========================================================
# КАСТОМНЫЙ ВХОД
# =========================================================
class CustomLoginView(LoginView):
    def get_success_url(self):
        # 1. Проверяем, с какой страницы пришёл пользователь
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        # 2. Если нет → стандартный редирект на дашборд
        return reverse_lazy('vault:dashboard')


# =========================================================
# ГЛАВНАЯ СТРАНИЦА (ВХОД)
# =========================================================
# ✅ УБРАН декоратор @require_http_methods(["GET"]), чтобы разрешить POST для формы входа!
def root_page(request):
    if request.user.is_authenticated:
        return redirect('vault:dashboard')

    return CustomLoginView.as_view(
        template_name='registration/login.html'
    )(request)


# =========================================================
# ВЫХОД ИЗ СИСТЕМЫ
# =========================================================
@require_http_methods(["GET", "POST"])
def custom_logout(request):
    logout(request)
    return redirect('home')


# =========================================================
# URL МАРШРУТЫ ПРОЕКТА
# =========================================================
urlpatterns = [
    # ✅ Оставляем только ОДИН путь для главной страницы
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
    path('reference/', include('reference.urls')),
    path('cars/', include('cars.urls')),
    path('master-plan/', include('master_plan.urls')),
    path('dispatcher/', include('dispatcher.urls')),

    # 🔹 Сброс пароля
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
]