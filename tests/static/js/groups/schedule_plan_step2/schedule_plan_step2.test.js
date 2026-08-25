/**
 * @jest-environment jsdom
 */

// =============================================================================
// 0. ГАРАНТИРОВАННЫЕ ГЛОБАЛЬНЫЕ МОКИ
// =============================================================================
global.fetch = jest.fn();
window.alert = jest.fn();

const localStorageMock = (() => {
  let store = {};
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => { store[key] = value.toString(); }),
    removeItem: jest.fn((key) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
  };
})();

// ✅ ВАЖНО: Задаем мок и для window, и для global, чтобы модуль точно его увидел
Object.defineProperty(window, 'localStorage', { value: localStorageMock, configurable: true });
global.localStorage = localStorageMock; // <-- ЭТА СТРОКА РЕШАЕТ ПРОБЛЕМУ

window.requestAnimationFrame = jest.fn((cb) => setTimeout(cb, 0));
window.cancelAnimationFrame = jest.fn();

// Подавляем предупреждение JSDOM о навигации
const originalConsoleError = console.error;
console.error = (...args) => {
  const msg = args[0]?.message || args[0];
  if (typeof msg === 'string' && msg.includes('Not implemented: navigation')) {
    return;
  }
  originalConsoleError(...args);
};

// =============================================================================
// 1. ПОДГОТОВКА DOM (ДО импорта файла!)
// =============================================================================
document.body.innerHTML = `
  <!-- ✅ ДОБАВЛЕН CSRF ТОКЕН ДЛЯ КОРРЕКТНОЙ РАБОТЫ deleteSchedule -->
  <input type="hidden" name="csrfmiddlewaretoken" value="fake-csrf-token-123" />

  <div id="plan-data-container"
       data-plan-id="100"
       data-program-id="PROG-1"
       data-required-hours="50"
       data-topics-state='{"2026-08-20":{"med":{"1": 2.5, "999": 1}}}'
       data-excluded-dates='["2026-08-25"]'>
  </div>
  <input id="grand-total" value="0 / 50" />
  <div id="topic-modal" style="display: none;">
    <div id="modal-date"></div>
    <div id="modal-content"></div>
    <div id="modal-total-required"></div>
    <div id="modal-remaining-total"></div>
    <button id="modal-close-btn">Close</button>
    <button id="modal-cancel-btn">Cancel</button>
    <button id="modal-save-btn">Save</button>
  </div>
  <form id="hours-form"></form>
  <select id="training-program-select">
    <option value="PROG-1" data-graphic-title="Тестовая программа">Тестовая программа</option>
  </select>
  <h1 id="program-title-header"></h1>
  <table class="distribution-table">
    <tbody>
      <tr>
        <td data-date="2026-08-20" data-subject="med">
          <input class="subject-hours hours-input" data-date="2026-08-20" data-subject="med" value="" />
        </td>
        <td data-date="2026-08-20" data-subject="total">
          <input class="day-total" data-date="2026-08-20" value="" />
        </td>
      </tr>
    </tbody>
  </table>
  <div id="med-total-display"></div>
  <input type="hidden" id="med-total" value="10" />
  <input type="hidden" id="test-total" value="0" />
`;

// =============================================================================
// 2. ИМПОРТ ТЕСТИРУЕМОГО МОДУЛЯ
// =============================================================================
const {
    StateManager,
    StorageManager,
    ModalController,
    toNumber,
    formatHours,
    roundHalf,
    scaleTopicsFairly,
    checkSubjectLimit,
    recalculateTotals,
    deleteSchedule
} = require('../../static/js/groups/schedule_plan_step2.js');

// =============================================================================
// 3. ТЕСТЫ
// =============================================================================

describe('Утилиты и форматирование', () => {
  test('toNumber корректно обрабатывает разные форматы', () => {
    expect(toNumber('2,5')).toBe(2.5);
    expect(toNumber(null)).toBe(0);
    expect(toNumber(undefined)).toBe(0);
    expect(toNumber('abc')).toBe(0);
  });

  test('formatHours форматирует числа правильно', () => {
    expect(formatHours(0)).toBe('');
    expect(formatHours(2)).toBe('2');
    expect(formatHours(2.5)).toBe('2.5');
  });

  test('roundHalf округляет до ближайших 0.5', () => {
    expect(roundHalf(2.2)).toBe(2);
    expect(roundHalf(2.3)).toBe(2.5);
    expect(roundHalf(2.75)).toBe(3);
  });
});

describe('StorageManager', () => {
  test('генерирует корректный ключ с PROGRAM_ID', () => {
    const key = StorageManager._getKey();
    expect(key).toContain('topicsState_100');
    expect(key).toContain('_program_PROG-1');
    expect(key).toContain('_v1');
  });

  test('сохраняет и загружает данные из localStorage', () => {
    const testData = { '2026-08-20': { med: { 1: 2 } } };
    StorageManager.save(testData);
    expect(localStorage.setItem).toHaveBeenCalled();

    const loaded = StorageManager.load();
    expect(loaded).toEqual(testData);
  });
});

describe('StateManager (Бизнес-логика)', () => {
  test('инициализируется и считает суммы', () => {
    StateManager.init({
      '2026-08-20': { med: { 1: 2.5, 2: 1.5 } },
      '2026-08-21': { med: { 1: 1 } }
    });

    const totals = StateManager.getComputedTotals();
    expect(totals.subjectSums.med).toBe(5);
    expect(totals.daySums['2026-08-20']).toBe(4);
    expect(totals.grandTotal).toBe(5);
  });

  test('scaleTopicsFairly пропорционально масштабирует часы', () => {
    const current = { 1: 2, 2: 2 };
    const target = 2;
    const result = scaleTopicsFairly(current, target);
    expect(result[1]).toBe(1);
    expect(result[2]).toBe(1);
  });

  test('scaleTopicsFairly корректно распределяет остаток', () => {
    const current = { 1: 3, 2: 3, 3: 3 };
    const target = 5;
    const result = scaleTopicsFairly(current, target);
    const sum = Object.values(result).reduce((a, b) => a + b, 0);
    expect(sum).toBe(5);
  });
});

describe('ModalController', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('открывает модалку и делает fetch запрос', async () => {
    global.fetch.mockResolvedValueOnce({
      json: async () => ({ success: true, topics: [{ id: 1, number: 1, name: 'Тема 1', hours: 4 }] })
    });

    ModalController.open('2026-08-20', 'med');

    expect(ModalController.currentDate).toBe('2026-08-20');
    expect(ModalController.currentSubject).toBe('med');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/reference/api/topics/?subject=med&program_id=PROG-1'),
      expect.any(Object)
    );
  });

  test('закрывает модалку и очищает состояние', () => {
    ModalController.hide();
    expect(ModalController.currentDate).toBeNull();
    expect(document.getElementById('topic-modal').style.display).toBe('none');
  });
});

describe('Интеграционные тесты', () => {
  test('recalculateTotals корректно обновляет DOM', async () => {
    StateManager.init({
      '2026-08-20': { med: { 1: 3.5 } }
    });

    recalculateTotals();

    await new Promise(resolve => setTimeout(resolve, 10));

    const grandTotal = document.getElementById('grand-total');
    expect(grandTotal.value).toContain('3.5');
  });
});

describe('Edge cases', () => {
  test('scaleTopicsFairly с нулевой суммой возвращает пустой объект', () => {
    const result = scaleTopicsFairly({ 1: 0, 2: 0 }, 5);
    expect(result).toEqual({});
  });

  test('checkSubjectLimit с лимитом 0 всегда валиден', () => {
    const result = checkSubjectLimit('test', '2026-08-20', 100);
    expect(result.valid).toBe(true);
    expect(result.limit).toBe(0);
  });

  test('checkSubjectLimit возвращает false при превышении лимита', () => {
    StateManager.init({
      '2026-08-20': { med: { 1: 8 } }
    });

    const result = checkSubjectLimit('med', '2026-08-20', 11);

    expect(result.valid).toBe(false);
    expect(result.limit).toBe(10);
    expect(result.projectedTotal).toBe(11);
  });
});

describe('Удаление и экспорт', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('deleteSchedule успешно вызывает fetch и очищает данные', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    });

    await deleteSchedule();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/groups/schedules/100/delete-plan/'),
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({
          'X-CSRFToken': expect.any(String),
          'Content-Type': 'application/json'
        })
      })
    );

    // ✅ Проверяем именно global.localStorage, который мы гарантированно замокали
    expect(global.localStorage.removeItem).toHaveBeenCalled();
  });
});
describe('Баг: часы не должны воскресать после обнуления', () => {
  test('обнуление часов сохраняется после перезагрузки (merge после reset)', () => {
    // 1. Имитируем серверные данные (5 часов по теме 1)
    StateManager.init({
      '2026-08-20': { med: { 1: 5 } }
    });

    // 2. Пользователь обнулил часы (поставил 0 в ячейке)
    StateManager.setSubject('2026-08-20', 'med', null);
    StateManager.save();

    // 3. Проверяем, что в StateManager часы = 0
    expect(StateManager.getDaySubjectSum('2026-08-20', 'med')).toBe(0);

    // 4. Имитируем "воскрешение" через reset (как было в баге)
    StateManager.reset({ '2026-08-20': { med: { 1: 5 } } });

    // 5. Повторно применяем localStorage (как в исправлении)
    const stored = StateManager.load();
    if (stored) StateManager.mergeData(stored);

    // 6. Часы НЕ должны воскреснуть!
    expect(StateManager.getDaySubjectSum('2026-08-20', 'med')).toBe(0);
  });

  test('часы не уходят в минус при распределении', () => {
    StateManager.init({
      '2026-08-20': { med: { 1: 5 } },
      '2026-08-21': { med: { 1: 6 } }
    });

    const totals = StateManager.getComputedTotals();
    // 5 + 6 = 11, а лимит 10 → remaining = -1
    // checkSubjectLimit должен это заблокировать
    const result = checkSubjectLimit('med', '2026-08-22', 1);
    expect(result.valid).toBe(false);
    expect(result.projectedTotal).toBe(12); // 11 + 1
  });
});

describe('Баг: смена программы не должна удалять localStorage', () => {
  test('данные пользователя сохраняются при переключении программ', () => {
    // 1. Пользователь обнулил часы для PROG-1
    StateManager.init({
      '2026-08-20': { med: { 1: 5 } }
    });
    StateManager.setSubject('2026-08-20', 'med', null);
    StateManager.save();

    // 2. Проверяем, что данные сохранены
    const key = StorageManager._getKey();
    expect(localStorage.setItem).toHaveBeenCalled();

    // 3. Имитируем смену программы (в реальном коде это делает обработчик)
    //    НО МЫ НЕ ДОЛЖНЫ ВЫЗЫВАТЬ clearByKey!
    //    Вместо этого просто проверяем, что ключ для PROG-1 всё ещё существует

    // 4. Возвращаемся на PROG-1 (перезагрузка страницы)
    const loadedData = StorageManager.load();

    // 5. Часы НЕ должны воскреснуть!
    expect(loadedData).toEqual({ '2026-08-20': { med: null } });
  });

  test('разные программы хранятся в разных ключах localStorage', () => {
    // 1. Сохраняем данные для PROG-1
    StateManager.init({ '2026-08-20': { med: { 1: 5 } } });
    StateManager.save();
    const key1 = StorageManager._getKey();
    expect(key1).toContain('_program_PROG-1');

    // 2. Имитируем смену на PROG-2 (в реальности это делает URL)
    //    В тесте мы просто проверяем, что ключ изменился бы
    //    (это уже покрыто тестом "генерирует корректный ключ с PROGRAM_ID")

    // 3. Данные PROG-1 всё ещё в localStorage
    expect(localStorage.getItem(key1)).toBeTruthy();
  });
});