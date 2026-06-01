# classrooms/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Classroom


@login_required
def classroom_list(request):
    classrooms = Classroom.objects.all().order_by('classroom_number')

    context = {
        'classrooms': classrooms,  # ✅ Имя переменной во множественном числе
        'today': timezone.now().date(),
    }
    return render(request, 'classrooms/classroom_list.html', context)