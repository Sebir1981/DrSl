# reference/views.py
import json
import traceback
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

# ✅ ЧИСТЫЕ ИМПОРТЫ (убран дублирующий Topic, используем только LessonTopic)
from .models import (
    LessonTopic, SubjectDictionary, GroupCategory,
    SubjectSet, TrainingProgram, ProgramSubject, ProgramTopic
)
from classrooms.models import Classroom
from teachers.models import Teacher
from masters.models import Master


# ==========================================
# Views: Темы занятий
# ==========================================

@login_required
def topic_list(request):
    current_code = request.GET.get('category', 'pdd')
    try:
        current_subject = SubjectDictionary.objects.get(short_name=current_code)
    except SubjectDictionary.DoesNotExist:
        current_subject = SubjectDictionary.objects.filter(short_name='pdd').first()
        if not current_subject:
            current_subject = SubjectDictionary.objects.first()
        current_code = current_subject.short_name if current_subject else 'pdd'

    all_subjects = SubjectDictionary.objects.all().order_by('name')
    topics = LessonTopic.objects.filter(subject=current_subject).order_by('topic_number')

    if request.method == 'POST' and 'topic_number' in request.POST:
        try:
            LessonTopic.objects.create(
                subject=current_subject,
                topic_number=int(request.POST['topic_number']),
                hours=0,
                content=request.POST['content']
            )
            messages.success(request, '✅ Тема добавлена')
        except Exception as e:
            messages.error(request, f'❌ Ошибка: {str(e)}')
        return redirect(f'{reverse("reference:topic_list")}?category={current_code}')

    subjects_with_counts = [
        {'code': s.short_name, 'name': s.name, 'count': LessonTopic.objects.filter(subject=s).count()}
        for s in all_subjects
    ]

    return render(request, 'reference/topic_list.html', {
        'topics': topics,
        'current_subject': current_subject,
        'current_code': current_code,
        'subjects_with_counts': subjects_with_counts,
        'title': 'Темы занятий'
    })


@login_required
def topic_delete(request, topic_id):
    topic = get_object_or_404(LessonTopic, pk=topic_id)
    subject_code = topic.subject.short_name if topic.subject else 'pdd'
    topic.delete()
    messages.success(request, '🗑️ Тема удалена')
    return redirect(f'{reverse("reference:topic_list")}?category={subject_code}')


@login_required
def reference_dashboard(request):
    return render(request, 'reference/dashboard.html', {
        'classrooms_count': Classroom.objects.count(),
        'teachers_count': Teacher.objects.count(),
        'masters_count': Master.objects.count(),
    })


# ==========================================
# 🔹 Управление справочником Предметов
# ==========================================

@login_required
def subject_list(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        short_name = request.POST.get('short_name')
        short_name_display = request.POST.get('short_name_display', '')

        if name and short_name:
            try:
                if SubjectDictionary.objects.filter(short_name=short_name).exists():
                    messages.error(request, f'⚠️ Код "{short_name}" уже занят.')
                else:
                    SubjectDictionary.objects.create(
                        name=name,
                        short_name=short_name,
                        short_name_display=short_name_display
                    )
                    messages.success(request, f'✅ Предмет "{name}" добавлен!')
                return redirect('reference:subject_list')
            except Exception as e:
                messages.error(request, f'❌ Ошибка: {e}')

    return render(request, 'reference/subject_list.html', {
        'subjects': SubjectDictionary.objects.all().order_by('name'),
        'title': 'Справочник предметов'
    })


@login_required
def subject_edit(request, pk):
    subject = get_object_or_404(SubjectDictionary, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')
        short_name = request.POST.get('short_name')
        short_name_display = request.POST.get('short_name_display', '')

        if name and short_name:
            try:
                if SubjectDictionary.objects.filter(short_name=short_name).exclude(pk=pk).exists():
                    messages.error(request, f'⚠️ Код "{short_name}" уже занят.')
                else:
                    subject.name = name
                    subject.short_name = short_name
                    subject.short_name_display = short_name_display
                    subject.save()
                    messages.success(request, f'✅ Предмет "{name}" обновлён!')
                    return redirect('reference:subject_list')
            except Exception as e:
                messages.error(request, f' Ошибка: {e}')

    return render(request, 'reference/subject_list.html', {
        'subjects': SubjectDictionary.objects.all().order_by('name'),
        'edit_subject': subject,
        'title': 'Редактирование предмета'
    })


@login_required
def subject_delete(request, pk):
    subject = get_object_or_404(SubjectDictionary, pk=pk)
    if LessonTopic.objects.filter(subject=subject).exists():
        messages.error(request, f'⚠️ Нельзя удалить "{subject.name}", так как к нему привязаны темы.')
    else:
        subject.delete()
        messages.success(request, f'🗑️ Предмет "{subject.name}" удалён.')
    return redirect('reference:subject_list')


# ==========================================
# 🔹 Управление программами обучения
# ==========================================

@login_required
def category_subjects_list(request):
    """
    Список программ обучения (вместо удалённой /reference/programs/)
    """
    # 🔹 Получаем plan_id из URL параметра (например, ?plan_id=19)
    plan_id = request.GET.get('plan_id')

    programs = TrainingProgram.objects.all().order_by('-created_at')

    return render(request, 'reference/category_subjects_list.html', {
        'programs': programs,
        'title': 'Программы обучения',
        'plan_id': plan_id,
    })


@login_required
def category_subjects_manage(request, category_code):
    category = get_object_or_404(GroupCategory, code=category_code)
    all_subjects = SubjectDictionary.objects.all().order_by('name')
    assigned_codes = set(category.subjects.values_list('short_name', flat=True))

    if request.method == 'POST':
        selected_codes = request.POST.getlist('subjects')
        category.subjects.set(SubjectDictionary.objects.filter(short_name__in=selected_codes))
        messages.success(request, f'✅ Для категории {category.code} сохранено {len(selected_codes)} предметов')
        return redirect('reference:category_subjects_manage', category_code=category.code)

    return render(request, 'reference/category_subjects_manage.html', {
        'category': category,
        'all_subjects': all_subjects,
        'assigned_codes': assigned_codes,
        'title': f'Предметы категории {category.code}'
    })


# ==========================================
#  Управление наборами предметов (SubjectSet)
# ==========================================

@login_required
def subject_sets_list(request):
    return render(request, 'reference/subject_sets_list.html', {
        'subject_sets': SubjectSet.objects.all().order_by('name'),
        'title': 'Наборы предметов по категориям'
    })


@login_required
def subject_set_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        category_codes = request.POST.getlist('categories')
        subject_codes = request.POST.getlist('subjects')

        if name:
            try:
                subject_set = SubjectSet.objects.create(name=name, description=description)
                if category_codes:
                    subject_set.categories.set(GroupCategory.objects.filter(code__in=category_codes))
                if subject_codes:
                    subject_set.subjects.set(SubjectDictionary.objects.filter(short_name__in=subject_codes))
                messages.success(request, f'✅ Набор "{name}" создан!')
                return redirect('reference:subject_sets_list')
            except Exception as e:
                messages.error(request, f' Ошибка: {e}')

    return render(request, 'reference/subject_set_form.html', {
        'title': 'Создать набор',
        'all_categories': GroupCategory.objects.all().order_by('code'),
        'all_subjects': SubjectDictionary.objects.all().order_by('name'),
        'mode': 'create'
    })


@login_required
def subject_set_edit(request, pk):
    subject_set = get_object_or_404(SubjectSet, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        category_codes = request.POST.getlist('categories')
        subject_codes = request.POST.getlist('subjects')

        if name:
            try:
                subject_set.name = name
                subject_set.description = description
                subject_set.save()
                subject_set.categories.set(GroupCategory.objects.filter(code__in=category_codes))
                subject_set.subjects.set(SubjectDictionary.objects.filter(short_name__in=subject_codes))
                messages.success(request, f'✅ Набор "{name}" обновлён!')
                return redirect('reference:subject_sets_list')
            except Exception as e:
                messages.error(request, f' Ошибка: {e}')

    return render(request, 'reference/subject_set_form.html', {
        'title': 'Редактировать набор',
        'subject_set': subject_set,
        'all_categories': GroupCategory.objects.all().order_by('code'),
        'all_subjects': SubjectDictionary.objects.all().order_by('name'),
        'mode': 'edit'
    })


@login_required
def subject_set_delete(request, pk):
    subject_set = get_object_or_404(SubjectSet, pk=pk)
    if request.method == 'POST':
        name = subject_set.name
        subject_set.delete()
        messages.success(request, f'🗑️ Набор "{name}" удалён')
        return redirect('reference:subject_sets_list')
    return render(request, 'reference/subject_set_delete.html', {
        'subject_set': subject_set,
        'title': 'Удаление набора'
    })


# =========================================================
#  API Эндпоинты
# =========================================================

@login_required
def api_get_topics(request):
    """API: получение тем с часами из конкретного учебного плана"""
    try:
        subject_code = request.GET.get('subject')
        program_id = request.GET.get('program_id')  # 🔹 Новый параметр

        if not subject_code:
            return JsonResponse({'success': False, 'error': 'subject required'}, status=400)

        # Получаем предмет
        subject = SubjectDictionary.objects.get(short_name=subject_code)

        topics_data = []

        # 🔹 1. Если известен ID программы (мы находимся в режиме редактирования плана)
        if program_id:
            try:
                program = TrainingProgram.objects.get(id=program_id)

                # Ищем этот предмет ВНУТРИ этой программы
                program_subject = ProgramSubject.objects.filter(
                    program=program,
                    subject=subject
                ).first()

                if program_subject:
                    # Берем темы И ИХ ЧАСЫ из связей программы
                    program_topics = ProgramTopic.objects.filter(
                        program_subject=program_subject
                    ).select_related('topic')

                    topics_data = [{
                        'id': pt.topic.id,
                        'number': pt.topic.topic_number,
                        'name': pt.topic.content,
                        'hours': float(pt.hours),  # ✅ БЕРЕМ ЧАСЫ ИЗ УЧЕБНОГО ПЛАНА!
                        'is_pz': 'пз' in pt.topic.content.lower(),
                    } for pt in program_topics.order_by('topic__topic_number')]

            except TrainingProgram.DoesNotExist:
                pass

        # 🔹 2. Если программа не указана или не найдена — берем из справочника (fallback)
        if not topics_data:
            topics = LessonTopic.objects.filter(subject=subject).order_by('topic_number')
            topics_data = [{
                'id': t.id,
                'number': t.topic_number,
                'name': t.content,
                'hours': float(t.hours) if t.hours else 0.0,
                'is_pz': 'пз' in t.content.lower(),
            } for t in topics]

        return JsonResponse({'success': True, 'topics': topics_data})

    except SubjectDictionary.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subject not found'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_get_subject_topics(request):
    """API: Получить темы для конкретного предмета (альтернативный эндпоинт)"""
    subject_code = request.GET.get('subject_code')
    if not subject_code:
        return JsonResponse({'success': False, 'error': 'subject_code required'}, status=400)

    try:
        subject = SubjectDictionary.objects.get(short_name=subject_code)
        topics = LessonTopic.objects.filter(subject=subject).order_by('topic_number')

        topics_data = [{
            'id': t.id,
            'number': t.topic_number,
            'name': t.content or '',
            'hours': float(getattr(t, 'hours', 0) or 0),
            'is_pz': bool(getattr(t, 'is_pz', False)),
        } for t in topics]

        return JsonResponse({'success': True, 'topics': topics_data})
    except SubjectDictionary.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subject not found'}, status=404)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_save_topics(request):
    """API: Сохранение распределения тем (заглушка/вспомогательный)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            selected_topics = data.get('topics', [])
            total_hours = sum(float(t.get('hours', 0)) for t in selected_topics)
            return JsonResponse({'success': True, 'total_hours': total_hours})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def api_get_subjects_by_category(request):
    """API: Получить предметы для категории (используется в план-графике)"""
    category_code = request.GET.get('category')
    if not category_code:
        return JsonResponse({'success': False, 'error': 'Category not specified'})

    subjects = SubjectDictionary.objects.filter(
        categories__code=category_code
    ).order_by('short_name')

    subjects_data = [{'code': s.short_name, 'name': s.name, 'hours': 0} for s in subjects]
    return JsonResponse({
        'success': True,
        'category': category_code,
        'subjects': subjects_data,
        'count': len(subjects_data)
    })


# ==========================================
# 🔹 Конструктор программ обучения
# ==========================================

import json  # ← Убедитесь, что импортирован


@login_required
def training_program_builder(request, pk=None):
    """Конструктор программы обучения: создание или редактирование"""

    # 1. Сначала определяем переменную program (или None)
    program = None
    if pk:
        program = get_object_or_404(TrainingProgram, pk=pk)

    # 2. Формируем заголовок
    title = f"Редактирование: {program.name}" if program else "Создание новой программы"

    # 3. Получаем справочники
    all_categories = GroupCategory.objects.all().order_by('code')
    all_subjects = SubjectDictionary.objects.all().order_by('short_name')

    # 4. 🔹 БЕЗОПАСНО: готовим данные только если программа существует
    program_subjects = {}
    if program:
        for ps in program.subjects.select_related('subject').prefetch_related('topics'):
            program_subjects[ps.subject.short_name] = {
                'is_enabled': ps.is_enabled,
                'hours': float(ps.hours),
                # 🔹 Ключи словаря должны быть строками для JSON
                'topics': {str(t.topic.id): float(t.hours) for t in ps.topics.all()}
            }

    # 5. Контекст для шаблона
    context = {
        'program': program,
        'title': title,
        'all_categories': all_categories,
        'all_subjects': all_subjects,
        # 🔹 Сериализуем в JSON с поддержкой кириллицы
        'program_subjects_json': json.dumps(program_subjects, ensure_ascii=False),
        'preselected_category': request.GET.get('category'),
    }

    return render(request, 'reference/training_program_builder.html', context)


@login_required
def category_subjects_manage_redirect(request, category_code):
    """Перенаправляет на конструктор программ с предвыбранной категорией"""
    return redirect(f'{reverse("reference:program_create")}?category={category_code}')


@login_required
def training_program_delete(request, pk):
    """Удаление программы обучения"""
    program = get_object_or_404(TrainingProgram, pk=pk)
    if request.method == 'POST':
        program_name = program.name
        program.delete()
        messages.success(request, f'️ Программа "{program_name}" удалена')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def training_program_save(request):
    """Сохранение программы обучения"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data = json.loads(request.body)
        program_id = data.get('program_id')
        name = data.get('name')
        total_hours = float(data.get('total_hours', 0))
        category_codes = data.get('categories', [])
        subjects_data = data.get('subjects', [])

        if program_id:
            program = TrainingProgram.objects.get(pk=program_id)
            program.name = name
            program.total_hours = total_hours
            program.save()
            program.categories.set(GroupCategory.objects.filter(code__in=category_codes))
        else:
            program = TrainingProgram.objects.create(name=name, total_hours=total_hours)
            program.categories.set(GroupCategory.objects.filter(code__in=category_codes))

        # Очищаем старые связи
        program.subjects.all().delete()

        # Добавляем новые предметы и темы
        for subj_data in subjects_data:
            if not subj_data.get('is_enabled'):
                continue

            subject = SubjectDictionary.objects.get(short_name=subj_data['code'])
            ps = ProgramSubject.objects.create(
                program=program,
                subject=subject,
                is_enabled=True,
                hours=subj_data.get('hours', 0)
            )

            for topic_data in subj_data.get('topics', []):
                topic = LessonTopic.objects.get(pk=topic_data['id'])
                ProgramTopic.objects.create(
                    program_subject=ps,
                    topic=topic,
                    hours=topic_data['hours']
                )

        return JsonResponse({
            'success': True,
            'message': 'Программа сохранена',
            'program_id': program.id,
            'redirect_url': '/reference/categories/'
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})