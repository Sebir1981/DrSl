// static/js/category-hint.js
(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        const categorySelect = document.querySelector('select.category-with-hint');
        if (!categorySelect || !categorySelect.dataset.hints) return;

        const hints = JSON.parse(categorySelect.dataset.hints.replace(/'/g, '"'));
        const hintBox = document.createElement('div');
        hintBox.id = 'category-hint-box';
        hintBox.style.cssText = 'font-size:12px;color:#64748b;margin-top:4px;padding:4px 8px;background:#f8fafc;border-radius:4px;';
        categorySelect.parentNode.insertBefore(hintBox, categorySelect.nextSibling);

        function updateHint() {
            const value = categorySelect.value;
            hintBox.textContent = hints[value] || '';
            hintBox.style.display = hints[value] ? 'block' : 'none';
        }

        categorySelect.addEventListener('change', updateHint);
        updateHint(); // Показать подсказку при загрузке
    });
})();