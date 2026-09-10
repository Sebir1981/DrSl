# vault/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

from .models import VaultEntry, VaultPermission
from .forms import AddVaultEntryForm

# Импорт моделей для дашборда
from groups.models import Group
from students.models import Student
from classrooms.models import Classroom
from teachers.models import Teacher
from masters.models import Master

# =========================================================
#  НАСТРОЙКИ ДОСТУПА
# =========================================================
# Роли, которым разрешено управлять записями (добавлять/редактировать)
MANAGE_ROLES = {'admin', 'director', 'secretary'}


# =========================================================
#  DASHBOARD
# =========================================================
@login_required
def dashboard(request):
    """Статистика хранилища"""
    context = {
        'groups_count': Group.objects.count(),
        'students_count': Student.objects.count(),
        'classrooms_count': Classroom.objects.count(),
        'teachers_count': Teacher.objects.count(),
        'masters_count': Master.objects.count(),
    }
    return render(request, 'vault/dashboard.html', context)


# =========================================================
# 📋 СПИСОК ЗАПИСЕЙ
# =========================================================
@login_required
def vault_list(request):
    """Отображение списка с фильтрацией по правам"""
    is_admin = request.user.is_superuser or request.user.groups.filter(name='admin').exists()

    if is_admin:
        entries = VaultEntry.objects.all().order_by('full_name')
    else:
        user_group_ids = request.user.groups.values_list('id', flat=True)
        entries = VaultEntry.objects.filter(
            allowed_roles__id__in=user_group_ids
        ).distinct().order_by('full_name')

    return render(request, 'vault/list.html', {'entries': entries})


# =========================================================
# 🔍 ДЕТАЛЬНЫЙ ПРОСМОТР
# =========================================================
@login_required
def vault_detail(request, entry_id):
    """Просмотр одной записи с расшифровкой пароля"""
    entry = get_object_or_404(VaultEntry, pk=entry_id)

    # 🔒 Проверка доступа
    is_admin = request.user.is_superuser or request.user.groups.filter(name='admin').exists()

    if not is_admin:
        # Проверяем индивидуальные разрешения
        try:
            # Если у пользователя есть хотя бы одно разрешение на эту запись, пускаем
            perm = VaultPermission.objects.get(user=request.user, vault_entry=entry)
        except VaultPermission.DoesNotExist:
            # Если нет индивидуальных прав, проверяем роли группы
            if not entry.allowed_roles.filter(id__in=request.user.groups.values_list('id', flat=True)).exists():
                return render(request, 'vault/access_denied.html', status=403)

    # 🔓 Расшифровка пароля
    decrypted_password = None
    try:
        decrypted_password = entry.get_decrypted_password()
    except (InvalidToken, Exception):
        messages.warning(request, "⚠️ Ошибка расшифровки: ключ изменён или повреждён.")
        decrypted_password = "❌ Ошибка расшифровки"

    return render(request, 'vault/detail.html', {
        'entry': entry,
        'decrypted_password': decrypted_password,
    })


# =========================================================
# ➕ ДОБАВЛЕНИЕ ЗАПИСИ
# =========================================================
@login_required
def add_entry(request):
    """Создание новой записи с шифрованием пароля"""
    user_roles = set(request.user.groups.values_list('name', flat=True))
    if not user_roles.intersection(MANAGE_ROLES):
        messages.error(request, "❌ У вас нет прав для добавления записей.")
        return redirect('vault:vault_list')

    if request.method == 'POST':
        form = AddVaultEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)

            # 🔐 Шифрование пароля
            fernet = Fernet(settings.VAULT_ENCRYPTION_KEY.encode())
            entry.encrypted_password = fernet.encrypt(
                form.cleaned_data['raw_password'].encode()
            ).decode()

            entry.created_by = request.user
            entry.save()

            messages.success(request, f"✅ Запись «{entry.full_name}» успешно добавлена!")
            return redirect('vault:vault_list')
    else:
        form = AddVaultEntryForm()

    return render(request, 'vault/add_entry.html', {'form': form})


# =========================================================
# ✏️ РЕДАКТИРОВАНИЕ ЗАПИСИ
# =========================================================
@login_required
def edit_entry(request, entry_id):
    """Обновление записи (пароль шифруется только если изменён)"""
    entry = get_object_or_404(VaultEntry, pk=entry_id)

    user_roles = set(request.user.groups.values_list('name', flat=True))
    if not user_roles.intersection(MANAGE_ROLES):
        messages.error(request, "❌ У вас нет прав для редактирования.")
        return redirect('vault:vault_detail', entry_id=entry.pk)

    if request.method == 'POST':
        form = AddVaultEntryForm(request.POST, instance=entry)
        if form.is_valid():
            updated_entry = form.save(commit=False)

            #  Если введён новый пароль — шифруем его
            new_pass = form.cleaned_data.get('raw_password')
            if new_pass:
                fernet = Fernet(settings.VAULT_ENCRYPTION_KEY.encode())
                updated_entry.encrypted_password = fernet.encrypt(new_pass.encode()).decode()
            # Иначе оставляем старый зашифрованный пароль без изменений

            updated_entry.save()
            messages.success(request, f"✅ Запись «{updated_entry.full_name}» обновлена!")
            return redirect('vault:vault_detail', entry_id=updated_entry.pk)
    else:
        form = AddVaultEntryForm(instance=entry)
        form.fields['raw_password'].required = False
        form.fields['raw_password'].help_text = "Оставьте пустым, если не хотите менять пароль"

    return render(request, 'vault/edit_entry.html', {'form': form, 'entry': entry})


# =========================================================
# ️ УДАЛЕНИЕ ЗАПИСИ (ТОЛЬКО АДМИНЫ)
# =========================================================
@login_required
def delete_entry(request, entry_id):
    """Удаление записи с подтверждением"""
    entry = get_object_or_404(VaultEntry, pk=entry_id)

    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):
        messages.error(request, "❌ Только администраторы могут удалять записи.")
        return redirect('vault:vault_detail', entry_id=entry.pk)

    if request.method == 'POST':
        entry_name = entry.full_name
        entry.delete()
        messages.success(request, f"🗑️ Запись «{entry_name}» удалена.")
        return redirect('vault:vault_list')

    return render(request, 'vault/confirm_delete.html', {'entry': entry})


# =========================================================
# 🔐 УПРАВЛЕНИЕ ПРАВАМИ ДОСТУПА (НОВОЕ)
# =========================================================

@login_required
def manage_permissions(request, entry_id):
    """Настройка доступов: иерархическая структура"""
    entry = get_object_or_404(VaultEntry, pk=entry_id)
    perm, _ = VaultPermission.objects.get_or_create(user=request.user, vault_entry=entry)

    if request.method == 'POST':

        # 🔹 Главные переключатели разделов
        perm.can_view_groups = request.POST.get('can_view_groups') == 'on'
        perm.can_view_students = request.POST.get('can_view_students') == 'on'
        perm.can_view_credits = request.POST.get('can_view_credits') == 'on'
        perm.can_view_reports = request.POST.get('can_view_reports') == 'on'
        perm.can_view_references = request.POST.get('can_view_references') == 'on'
        perm.can_view_vault = request.POST.get('can_view_vault') == 'on'

        # 🔹 Группы
        perm.perm_grp_create = request.POST.get('perm_grp_create') == 'on'
        perm.perm_grp_list = request.POST.get('perm_grp_list') == 'on'
        perm.perm_grp_schedule1 = request.POST.get('perm_grp_schedule1') == 'on'
        perm.perm_grp_schedule2 = request.POST.get('perm_grp_schedule2') == 'on'
        perm.perm_grp_timetable = request.POST.get('perm_grp_timetable') == 'on'
        perm.perm_grp_close = request.POST.get('perm_grp_close') == 'on'

        # 🔹 Учащиеся (обновленный список)
        perm.perm_stu_add = request.POST.get('perm_stu_add') == 'on'
        perm.perm_stu_info = request.POST.get('perm_stu_info') == 'on'
        perm.perm_stu_transfer = request.POST.get('perm_stu_transfer') == 'on'
        perm.perm_stu_suspend = request.POST.get('perm_stu_suspend') == 'on'
        perm.perm_stu_refusal = request.POST.get('perm_stu_refusal') == 'on'
        perm.perm_stu_dismiss = request.POST.get('perm_stu_dismiss') == 'on'
        perm.perm_stu_contract_renew = request.POST.get('perm_stu_contract_renew') == 'on'
        perm.perm_stu_payments = request.POST.get('perm_stu_payments') == 'on'
        perm.perm_stu_notifications = request.POST.get('perm_stu_notifications') == 'on'


        # 🔹 Зачёты
        perm.perm_cred_dashboard = request.POST.get('perm_cred_dashboard') == 'on'
        perm.perm_cred_add = request.POST.get('perm_cred_add') == 'on'
        perm.perm_cred_reports = request.POST.get('perm_cred_reports') == 'on'

        # 🔹 Отчёты
        perm.perm_rep_dashboard = request.POST.get('perm_rep_dashboard') == 'on'
        perm.perm_rep_generate = request.POST.get('perm_rep_generate') == 'on'
        perm.perm_rep_export = request.POST.get('perm_rep_export') == 'on'

        # 🔹 Справочники
        perm.perm_ref_classrooms = request.POST.get('perm_ref_classrooms') == 'on'
        perm.perm_ref_teachers = request.POST.get('perm_ref_teachers') == 'on'
        perm.perm_ref_masters = request.POST.get('perm_ref_masters') == 'on'
        perm.perm_ref_topics = request.POST.get('perm_ref_topics') == 'on'
        perm.perm_ref_categories = request.POST.get('perm_ref_categories') == 'on'

        # 🔹 Хранилище
        perm.perm_vault_list = request.POST.get('perm_vault_list') == 'on'
        perm.perm_vault_add = request.POST.get('perm_vault_add') == 'on'
        perm.perm_vault_manage = request.POST.get('perm_vault_manage') == 'on'

        # 🔹 Админка
        perm.perm_admin_access = request.POST.get('perm_admin_access') == 'on'

        perm.save()
        messages.success(request, "✅ Настройки доступа сохранены!")
        return redirect('vault:manage_permissions', entry_id=entry.pk)

    return render(request, 'vault/manage_permissions.html', {'entry': entry, 'perm': perm})


# =========================================================
# 🔐 API: ПРОВЕРКА ДОСТУПА
# =========================================================
@login_required
def check_access(request, entry_id):
    """API: Проверка доступа пользователя к разделам"""
    entry = get_object_or_404(VaultEntry, pk=entry_id)
    user = request.user

    # Админы видят всё
    if user.is_superuser or user.groups.filter(name='admin').exists():
        return JsonResponse({'access': 'full'})

    # Проверяем индивидуальные разрешения
    try:
        perm = VaultPermission.objects.get(user=user, vault_entry=entry)
        return JsonResponse({
            'access': 'partial',
            'permissions': {
                # 🔹 Основные разделы
                'groups': perm.can_view_groups,
                'students': perm.can_view_students,
                'credits': perm.can_view_credits,
                'reports': perm.can_view_reports,
                'references': perm.can_view_references,
                'vault': perm.can_view_vault,
                'admin': perm.can_view_admin,

                # 🔹 Группы (подробные права)
                'perm_grp_create': perm.perm_grp_create,
                'perm_grp_list': perm.perm_grp_list,
                'perm_grp_schedule1': perm.perm_grp_schedule1,
                'perm_grp_schedule2': perm.perm_grp_schedule2,
                'perm_grp_timetable': perm.perm_grp_timetable,
                'perm_grp_close': perm.perm_grp_close,

                # 🔹 Учащиеся
                'perm_stu_add': perm.perm_stu_add,
                'perm_stu_info': perm.perm_stu_info,
                'perm_stu_transfer': perm.perm_stu_transfer,
                'perm_stu_suspend': perm.perm_stu_suspend,
                'perm_stu_refusal': perm.perm_stu_refusal,
                'perm_stu_dismiss': perm.perm_stu_dismiss,
                'perm_stu_contract_renew': perm.perm_stu_contract_renew,
                'perm_stu_payments': perm.perm_stu_payments,
                'perm_stu_notifications': perm.perm_stu_notifications,

                # 🔹 Зачёты
                'perm_cred_dashboard': perm.perm_cred_dashboard,
                'perm_cred_add': perm.perm_cred_add,
                'perm_cred_reports': perm.perm_cred_reports,

                # 🔹 Отчёты
                'perm_rep_dashboard': perm.perm_rep_dashboard,
                'perm_rep_generate': perm.perm_rep_generate,
                'perm_rep_export': perm.perm_rep_export,

                #  Справочники
                'perm_ref_classrooms': perm.perm_ref_classrooms,
                'perm_ref_teachers': perm.perm_ref_teachers,
                'perm_ref_masters': perm.perm_ref_masters,
                'perm_ref_topics': perm.perm_ref_topics,
                'perm_ref_categories': perm.perm_ref_categories,

                # 🔹 Хранилище
                'perm_vault_list': perm.perm_vault_list,
                'perm_vault_add': perm.perm_vault_add,
                'perm_vault_manage': perm.perm_vault_manage,

                # 🔹 Админка
                'perm_admin_access': perm.perm_admin_access,
            }
        })
    except VaultPermission.DoesNotExist:
        return JsonResponse({'access': 'none'})