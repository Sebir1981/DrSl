     // static/js/phone-mask.js
(function() {
    'use strict';

    function applyPhoneMask(input) {
        if (input.dataset.maskApplied) return;
        input.dataset.maskApplied = '1';

        const formatPhone = (value) => {
            const digits = value.replace(/\D/g, '');
            if (!digits) return '';
            if (digits.startsWith('375')) {
                return '+375 ' + formatAfterCode(digits.slice(3));
            }
            if (digits.startsWith('8')) {
                return '+375 ' + formatAfterCode(digits.slice(1));
            }
            return '+375 ' + formatAfterCode(digits);
        };

        const formatAfterCode = (digits) => {
            const d = digits.slice(0, 9);
            let result = '';
            if (d.length > 0) result += '(' + d.slice(0, 2);
            if (d.length >= 3) result += ') ' + d.slice(2, 5);
            if (d.length >= 6) result += '-' + d.slice(5, 7);
            if (d.length >= 8) result += '-' + d.slice(7, 9);
            return result;
        };

        input.addEventListener('input', function(e) {
            e.target.value = formatPhone(e.target.value);
        });

        input.addEventListener('blur', function(e) {
            const digits = e.target.value.replace(/\D/g, '');
            if (digits.length > 0 && digits.length < 12) {
                e.target.value = '';
            }
        });

        if (input.value) {
            input.value = formatPhone(input.value);
        }
    }

    function initAllPhoneInputs() {
        document.querySelectorAll('input#id_phone_student, input[data-phone-mask="true"]').forEach(applyPhoneMask);
    }

    document.addEventListener('DOMContentLoaded', initAllPhoneInputs);
    document.addEventListener('shown.bs.tab', initAllPhoneInputs);
    setTimeout(initAllPhoneInputs, 100);

    if (window.MutationObserver) {
        const observer = new MutationObserver(initAllPhoneInputs);
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();