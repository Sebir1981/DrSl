# tests/test_widgets.py
from django.test import TestCase
from datetime import date, datetime
from DrSl.widgets import RuDateWidget


class RuDateWidgetTest(TestCase):
    def test_format_date(self):
        widget = RuDateWidget()
        result = widget.format_value(date(2026, 8, 13))
        self.assertEqual(result, '13.08.2026')

    def test_format_datetime(self):
        widget = RuDateWidget()
        result = widget.format_value(datetime(2026, 8, 13, 10, 30))
        self.assertEqual(result, '13.08.2026')

    def test_format_string(self):
        widget = RuDateWidget()
        result = widget.format_value('2026-08-13')
        self.assertEqual(result, '13.08.2026')

    def test_format_none(self):
        widget = RuDateWidget()
        result = widget.format_value(None)
        self.assertEqual(result, '')

    def test_render(self):
        widget = RuDateWidget()
        html = widget.render('date_field', '2026-08-13')
        self.assertIn('date_field', html)
        self.assertIn('13.08.2026', html)