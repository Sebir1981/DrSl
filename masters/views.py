from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import MasterPouts
from .forms import MasterPoutsForm
from django.http import JsonResponse
from django.template.loader import render_to_string


@login_required
def master_pouts_list(request):
    """Список мастеров ПОУТС"""
    masters = MasterPouts.objects.select_related('car').all()

    query = request.GET.get('q', '').strip()
    if query:
        masters = masters.filter(
            Q(last_name__icontains=query) |
            Q(first_name__icontains=query) |
            Q(patronymic__icontains=query) |
            Q(phone__icontains=query)
        )

    return render(request, 'masters/master_pouts_list.html', {
        'masters': masters,
        'title': 'Мастера ПОУТС'
    })


@login_required
def master_pouts_add(request):
    """Добавление мастера ПОУТС"""
    if request.method == 'POST':
        form = MasterPoutsForm(request.POST)
        if form.is_valid():
            master = form.save()
            messages.success(request, f'✅ Мастер {master.full_name} добавлен!')
            return redirect('masters:master_pouts_list')
    else:
        form = MasterPoutsForm()

    return render(request, 'masters/master_pouts_form.html', {
        'form': form,
        'title': 'Добавить мастера ПОУТС',
        'is_edit': False
    })


@login_required
def master_pouts_edit(request, pk):
    """Редактирование мастера ПОУТС"""
    master = get_object_or_404(MasterPouts, pk=pk)

    if request.method == 'POST':
        form = MasterPoutsForm(request.POST, instance=master)
        if form.is_valid():
            master = form.save()
            messages.success(request, f'✅ Данные мастера {master.full_name} обновлены!')
            return redirect('masters:master_pouts_list')
    else:
        form = MasterPoutsForm(instance=master)

    return render(request, 'masters/master_pouts_form.html', {
        'form': form,
        'title': 'Редактировать мастера ПОУТС',
        'is_edit': True,
        'master': master
    })


@login_required
def master_pouts_delete(request, pk):
    """Удаление мастера ПОУТС"""
    master = get_object_or_404(MasterPouts, pk=pk)

    if request.method == 'POST':
        full_name = master.full_name
        master.delete()
        messages.success(request, f'️ Мастер {full_name} удалён')
        return redirect('masters:master_pouts_list')

    return render(request, 'masters/master_pouts_confirm_delete.html', {
        'master': master
    })


def master_pouts_search_api(request):
    """API для живого поиска мастеров"""
    query = request.GET.get('q', '').strip()
    item_id = request.GET.get('id', '').strip()

    masters = MasterPouts.objects.select_related('car').all()

    # Если запрошен конкретный ID — возвращаем только его
    if item_id:
        masters = masters.filter(pk=int(item_id))
    elif query:
        masters = masters.filter(
            Q(last_name__icontains=query) |
            Q(first_name__icontains=query) |
            Q(patronymic__icontains=query) |
            Q(phone__icontains=query)
        )[:10]  # Ограничиваем до 10 подсказок

    # Формируем подсказки
    suggestions = []
    for m in masters:
        full_name = f"{m.last_name} {m.first_name} {m.patronymic}".strip()
        suggestions.append({
            'id': m.pk,
            'suggestion_text': f"👤 {full_name} • 📞 {m.phone}"
        })

    # Формируем строки таблицы
    rows = []
    for master in masters:
        row_html = render_to_string('masters/_master_row.html', {'master': master}, request=request)
        rows.append(row_html)

    return JsonResponse({
        'suggestions': suggestions,
        'rows': rows
    })