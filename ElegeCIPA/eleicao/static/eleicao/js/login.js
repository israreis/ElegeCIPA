(function () {
  const ACTIVE = ['bg-primary', 'text-white'];
  const INACTIVE = ['text-gray-600'];

  const tabs = {
    eleitor: {
      button: document.getElementById('btnEleitor'),
      form: document.getElementById('formEleitor'),
    },
    admin: {
      button: document.getElementById('btnAdmin'),
      form: document.getElementById('formAdmin'),
    },
  };

  function showTab(name) {
    Object.entries(tabs).forEach(([key, { button, form }]) => {
      const active = key === name;
      form.classList.toggle('hidden', !active);
      button.classList.remove(...ACTIVE, ...INACTIVE);
      button.classList.add(...(active ? ACTIVE : INACTIVE));
    });
  }

  function digitsOnly(input) {
    if (!input) return;
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g, '');
    });
  }

  Object.entries(tabs).forEach(([key, { button }]) => {
    button.addEventListener('click', () => showTab(key));
  });

  digitsOnly(document.getElementById('id_cpf'));
  digitsOnly(document.getElementById('id_matricula'));

  showTab((document.getElementById('login') || {dataset: {}}).dataset.activeTab || 'eleitor');
})();
