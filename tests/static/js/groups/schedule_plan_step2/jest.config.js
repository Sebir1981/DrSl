module.exports = {
  // ✅ Явно указываем, что корень проекта находится на 2 уровня выше (C:\django\DrSl)
  rootDir: '../../',

  testEnvironment: 'jsdom',

  // ✅ Теперь <rootDir> = C:\django\DrSl, и этот путь сработает идеально
  setupFilesAfterEnv: ['<rootDir>/tests/schedule_plan_step2/jest.setup.js'],

  // ✅ Искать тесты в папке модуля
  testMatch: [
    '<rootDir>/tests/schedule_plan_step2/**/*.test.js'
  ],

  // ✅ Покрытие для исходного файла (относительно настоящего корня)
  collectCoverageFrom: [
    'static/js/groups/schedule_plan_step2.js',
    '!**/node_modules/**',
    '!**/vendor/**'
  ],

  // ✅ Отчёты о покрытии сохраняем в папку модуля
  coverageDirectory: '<rootDir>/tests/schedule_plan_step2/coverage',

  coverageReporters: ['text', 'lcov', 'html'],

  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50
    }
  }
};