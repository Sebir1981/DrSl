// jest.setup.js
// Этот файл настраивает окружение для Jest перед каждым тестом

// Мок localStorage с поддержкой Jest spy
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => { store[key] = value.toString(); }),
    removeItem: jest.fn((key) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Мок fetch (глобально для всех тестов)
global.fetch = jest.fn();

// Мок window.location
delete window.location;
window.location = {
  href: 'http://localhost/?program_id=PROG-1&debug=true',
  search: '?program_id=PROG-1&debug=true',
  assign: jest.fn()
};

// Мок AbortController (для jsdom)
if (typeof window.AbortController === 'undefined') {
  window.AbortController = class AbortController {
    constructor() { this.signal = { aborted: false }; }
    abort() { this.signal.aborted = true; }
  };
}