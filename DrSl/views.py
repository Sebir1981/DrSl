from django.contrib.auth.views import LoginView
from django.shortcuts import redirect



class CustomLoginView(LoginView):
    """Кастомный вход: всегда редиректит на дашборд, игнорируя next"""

    def get_success_url(self):
        # ✅ Игнорируем любой ?next=... и всегда кидаем на дашборд
        return '/vault/'  # Или используйте reverse_lazy('vault:dashboard')