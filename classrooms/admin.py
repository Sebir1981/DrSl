# classrooms/admin.py
from django.contrib import admin
from django import forms
from .models import Classroom
from DrSl.widgets import RuDateWidget


class ClassroomAdminForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = '__all__'
        widgets = {
            # ✅ УБРАНО: style='width:...' → ширина теперь только в CSS
            'classroom_number': forms.TextInput(),
            'address': forms.TextInput(),
            'capacity': forms.NumberInput(),
            'contract_number': forms.TextInput(),
            'contract_start': RuDateWidget(),
            'contract_end': RuDateWidget(),
            'san_certificate_valid_until': RuDateWidget(),
        }


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    form = ClassroomAdminForm
    list_display = ('classroom_number', 'address_short', 'capacity', 'contract_end_display', 'ses_display')
    list_filter = ('capacity', 'contract_end', 'san_certificate_valid_until')
    search_fields = ('address',)

    fieldsets = (
        (None, {
            'fields': (
                ('classroom_number',),
                ('address', 'capacity'),
                ('contract_number',),
                ('contract_start', 'contract_end'),
                'contract_file',
                'san_certificate_valid_until',
            ),
            'classes': ('no-border',),
        }),
    )

    @admin.display(description="Адрес", ordering='address')
    def address_short(self, obj):
        return (obj.address[:40] + '…') if obj.address and len(obj.address) > 40 else obj.address or '—'

    @admin.display(description="Договор до", ordering='contract_end')
    def contract_end_display(self, obj):
        return obj.contract_end.strftime('%d.%m.%Y') if obj.contract_end else '—'

    @admin.display(description="СЭС", ordering='san_certificate_valid_until')
    def ses_display(self, obj):
        return obj.san_certificate_valid_until.strftime('%d.%m.%Y') if obj.san_certificate_valid_until else '—'

    class Media:
        # ✅ Cache-busting + только этот CSS отвечает за ширину
        css = {'all': ('css/admin-horizontal.css?v=3',)}