document.addEventListener('DOMContentLoaded', () => {
  const description = document.getElementById('description');
  const counter = document.getElementById('char-count');
  if (description && counter) {
    const update = () => { counter.textContent = `${description.value.length} / 3000`; };
    description.addEventListener('input', update);
    update();
  }
  document.querySelectorAll('.flash button').forEach(button => button.addEventListener('click', () => button.parentElement.remove()));
});
