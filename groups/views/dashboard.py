# groups/views/dashboard.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from groups.models import Group
from reference.models import GroupCategory


@login_required
def groups_dashboard(request):
    """Панель управления разделом 'Группы'"""
    context = {
        'total_groups': Group.objects.count(),
        'active_groups': Group.objects.filter(status='active').count(),
        'categories_count': GroupCategory.objects.count(),
    }
    return render(request, 'groups/dashboard.html', context)