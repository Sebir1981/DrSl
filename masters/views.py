from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Master

@login_required
def master_list(request):
    masters = Master.objects.all().order_by('last_name')
    return render(request, 'masters/master_list.html', {'masters': masters})