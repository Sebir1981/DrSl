/**
 * Универсальный модуль живого поиска и автоподсказок
 */
document.addEventListener('DOMContentLoaded', function() {
    // Находим поле ввода и контейнер подсказок
    const searchInput = document.querySelector('[data-live-search="true"]');
    const suggestionsBox = document.getElementById('search-suggestions');

    if (!searchInput) return;

    // Получаем данные для AJAX
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

        // Если строка пустая — скрываем подсказки и ничего не делаем (таблица уже полная)
        if (query.length === 0) {
            suggestionsBox.style.display = 'none';
            return;
        }

        // Разрешаем поиск даже по 1 символу, но с задержкой 300 мс
        debounceTimer = setTimeout(() => {
            fetch(`${apiUrl}?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    // Отрисовка подсказок (из suggestions)
                    if (data.suggestions && data.suggestions.length > 0) {
                        let html = '';
                        data.suggestions.forEach(item => {
                            html += `<div class="suggestion-item" data-id="${item.id}" style="padding:8px 12px;cursor:pointer;border-bottom:1px solid #f1f5f9;font-size:14px;">
                                        ${item.suggestion_text}
                                     </div>`;
                        });
                        suggestionsBox.innerHTML = html;
                        suggestionsBox.style.display = 'block';
                    } else {
                        suggestionsBox.innerHTML = '<div style="padding:8px 12px;color:#64748b;font-size:14px;">Ничего не найдено</div>';
                        suggestionsBox.style.display = 'block';
                    }
                })
                .catch(err => console.error(err));
        }, 300); // Задержка 300 мс для 1 символа
    });

    // 3. Обработка клика по подсказке (фильтрация таблицы)
    document.addEventListener('click', function(e) {
        if (e.target.closest('.suggestion-item')) {
            const item = e.target.closest('.suggestion-item');
            const studentId = item.getAttribute('data-id');

            // Устанавливаем значение в поле ввода (для красоты)
            searchInput.value = item.textContent.trim();
            suggestionsBox.style.display = 'none';

            // Применяем фильтрацию таблицы по найденному ID
            fetch(`${apiUrl}?student_id=${studentId}`)
                .then(response => response.json())
                .then(data => {
                    targetElement.innerHTML = '';
                    if (data.rows.length === 0) {
                        const colSpan = targetElement.getAttribute('data-empty-colspan') || 6;
                        targetElement.innerHTML = `<tr><td colspan="${colSpan}" class="text-center">Ничего не найдено</td></tr>`;
                    } else {
                        data.rows.forEach(row => {
                            targetElement.insertAdjacentHTML('beforeend', row);
                        });
                    }
                });
        }
    });

    // 4. Скрыть подсказки при клике вне их области
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#search-suggestions') && !e.target.closest('#search-input')) {
            suggestionsBox.style.display = 'none';
        }
    });
});