(function () {
  const input = document.querySelector('[data-file-input]');
  const label = document.getElementById('fileName');

  if (!input || !label) return;

  const defaultText = label.textContent;
  input.addEventListener('change', () => {
    label.textContent = input.files.length > 0 ? input.files[0].name : defaultText;
  });
})();
