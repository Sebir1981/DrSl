/**
 * Универсальный модуль живого поиска и автоподсказок
 * static/js/live_search.js
 */
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('[data-live-search="true"]');
    const suggestionsBox = document.getElementById('search-suggestions');

    if (!searchInput) return;

    const targetId = searchInput.getAttribute('data-target');
    const targetElement = document.getElementById(targetId);
    const apiUrl = searchInput.getAttribute('data-api-url');

    if (!targetElement || !apiUrl) {
        console.warn('Live Search: Неверные атрибуты data-target или data-api-url.');
        return;
    }

    let debounceTimer;

    // 1. Слушаем ввод текста
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();

        // Если строка пустая — скрываем подсказки и восстанавливаем таблицу
        if (query.length === 0) {
            suggestionsBox.style.display = 'none';
            // Перезагружаем страницу, чтобы показать полный список
            window.location.search = '';
            return;
        }

        // Задержка 300 мс
        debounceTimer = setTimeout(() => {
            fetch(`${apiUrl}?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.suggestions && data.suggestions.length > 0) {
                        let html = '';
                        data.suggestions.forEach(item => {
                            html += `<div class="suggestion-item" data-id="${item.id}" style="padding:8px 12px;cursor:pointer;border-bottom:1px solid #f1f5f9;font-size:14px;background:white;">
                                        ${item.suggestion_text}
                                     </div>`;
                        });
                        suggestionsBox.innerHTML = html;
                        suggestionsBox.style.display = 'block';
                    } else {
                        suggestionsBox.innerHTML = '<div style="padding:8px 12px;color:#64748b;font-size:14px;background:white;">Ничего не найдено</div>';
                        suggestionsBox.style.display = 'block';
                    }
                })
                .catch(err => console.error(err));
        }, 300);
    });

    // 2. Обработка клика по подсказке
    document.addEventListener('click', function(e) {
        if (e.target.closest('.suggestion-item')) {
            const item = e.target.closest('.suggestion-item');
            const itemId = item.getAttribute('data-id');

            searchInput.value = item.textContent.trim();
            suggestionsBox.style.display = 'none';

            fetch(`${apiUrl}?id=${itemId}`)
                .then(response => response.json())
                .then(data => {
                    targetElement.innerHTML = '';
                    if (data.rows.length === 0) {
                        const colSpan = targetElement.getAttribute('data-empty-colspan') || 6;
                        targetElement.innerHTML = `<tr><td colspan="${colSpan}" class="empty-state">Ничего не найдено</td></tr>`;
                    } else {
                        data.rows.forEach(row => {
                            targetElement.insertAdjacentHTML('beforeend', row);
                        });
                    }
                });
        }
    });

    // 3. Скрыть подсказки при клике вне их области
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#search-suggestions') && !e.target.closest('[data-live-search]')) {
            suggestionsBox.style.display = 'none';
        }
    });
});