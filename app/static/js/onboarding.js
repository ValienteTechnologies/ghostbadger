(function () {
  "use strict";

  var card      = document.querySelector('.onboarding__card');
  var formPw    = document.getElementById('form-password');
  var formTok   = document.getElementById('form-token');
  var link      = document.getElementById('toggle-link');
  var subtitle  = document.getElementById('form-subtitle');
  var showToken = card.dataset.initialMode === 'token';

  function update() {
    if (showToken) {
      formPw.classList.add('onboarding__form--hidden');
      formTok.classList.remove('onboarding__form--hidden');
      subtitle.textContent = 'Enter your Ghostwriter API token to get started.';
      link.textContent = 'Sign in with username & password instead';
    } else {
      formTok.classList.add('onboarding__form--hidden');
      formPw.classList.remove('onboarding__form--hidden');
      subtitle.textContent = 'Sign in with your Ghostwriter credentials.';
      link.textContent = 'Paste a JWT token instead';
    }
  }

  link.addEventListener('click', function (e) {
    e.preventDefault();
    showToken = !showToken;
    update();
  });
}());
