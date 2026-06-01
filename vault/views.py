# vault/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

# ✅ ИМПОРТЫ МОДЕЛЕЙ (РАЗДЕЛЕНЫ ПО ПРАВИЛЬНЫМ ПРИЛОЖЕНИЯМ)
from groups.models import Group          # ✅ Исправлено: Group теперь из groups
from students.models import Student      # ✅ Student остаётся в students
from classrooms.models import Classroom
from teachers.models import Teacher
from masters.models import Master
from .models import VaultEntry
from .forms import AddVaultEntryForm


# =========================================================
# РОЛИ, КОТОРЫМ РАЗРЕШЕНО ДОБАВЛЕНИЕ ЗАПИСЕЙ
# =========================================================
ALLOWED_ADD_ROLES = {
    'admin',
    'director',
    'secretary',
}


# =========================================================
# DASHBOARD
# =========================================================
@login_required
def dashboard(request):
    context = {
        'groups_count': Group.objects.count(),
        'students_count': Student.objects.count(),
        'classrooms_count': Classroom.objects.count(),
        'teachers_count': Teacher.objects.count(),
        'masters_count': Master.objects.count(),
        'instructors_count': 0,
        'cars_count': 0,
    }
    return render(request, 'vault/dashboard.html', context)


# =========================================================
# СПИСОК ДОСТУПНЫХ ЗАПИСЕЙ
# =========================================================
@login_required
def vault_list(request):
    user_group_ids = request.user.groups.values_list('id', flat=True)
    entries = (
        VaultEntry.objects
        .filter(allowed_roles__id__in=user_group_ids)
        .distinct()
        .order_by('title')
    )
    return render(request, 'vault/list.html', {'entries': entries})


# =========================================================
# ПРОСМОТР ОДНОЙ ЗАПИСИ
# =========================================================
@login_required
def vault_detail(request, pk):
    entry = get_object_or_404(VaultEntry, pk=pk)
    has_access = entry.allowed_roles.filter(
        id__in=request.user.groups.values_list('id', flat=True)
    ).exists()

    if not has_access:
        return render(request, 'vault/access_denied.html', status=403)

    try:
        decrypted_password = entry.get_decrypted_password()
    except (InvalidToken, Exception):
        decrypted_password = "❌ Ошибка: ключ шифрования изменён или повреждён"
        messages.error(request, decrypted_password)

    return render(
        request,
        'vault/detail.html',
        {
            'entry': entry,
            'decrypted_password': decrypted_password,
        }
    )


# =========================================================
# ДОБАВЛЕНИЕ НОВОЙ ЗАПИСИ
# =========================================================
@login_required
def add_entry(request):
    user_roles = set(request.user.groups.values_list('name', flat=True))

    if not user_roles.intersection(ALLOWED_ADD_ROLES):
        messages.error(request, "У вас нет прав для добавления записей.")
        return redirect('vault:vault_list')

    if request.method == 'POST':
        form = AddVaultEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            fernet = Fernet(settings.VAULT_ENCRYPTION_KEY.encode())
            encrypted_password = fernet.encrypt(
                form.cleaned_data['raw_password'].encode()
            ).decode()
            entry.encrypted_password = encrypted_password
            entry.created_by = request.user
            entry.save()
            messages.success(request, f"Запись '{entry.title}' успешно добавлена!")
            return redirect('vault:vault_list')
    else:
        form = AddVaultEntryForm()

    return render(request, 'vault/add_entry.html', {'form': form})