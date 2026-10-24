/* The portfolio is fully readable without JavaScript. These are optional enhancements. */
const cards = [...document.querySelectorAll('.project-card')];
const filters = [...document.querySelectorAll('[data-filter]')];
const search = document.querySelector('#project-search');
const count = document.querySelector('#project-count');
const empty = document.querySelector('#no-projects');
let selected = 'all';
function filterProjects() {
  const query = (search?.value || '').trim().toLocaleLowerCase();
  let visible = 0;
  cards.forEach(card => {
    const match = (selected === 'all' || card.dataset.category.split('|').includes(selected)) && card.dataset.search.includes(query);
    card.hidden = !match;
    if (match) visible++;
  });
  if (count) count.textContent = `${visible} ${visible === 1 ? 'project' : 'projects'}`;
  if (empty) empty.hidden = visible !== 0;
}
if (cards.length) {
  document.querySelector('.project-toolbar')?.removeAttribute('hidden');
  filters.forEach(button => button.addEventListener('click', () => {
    selected = button.dataset.filter;
    filters.forEach(other => other.setAttribute('aria-pressed', String(other === button)));
    filterProjects();
  }));
  search?.addEventListener('input', filterProjects);
  document.querySelector('#reset-projects')?.addEventListener('click', () => {
    if (search) search.value = '';
    filters.find(button => button.dataset.filter === 'all')?.click();
    search?.focus();
  });
}

const galleryLinks = [...document.querySelectorAll('[data-lightbox]')];
const dialog = document.querySelector('#image-lightbox');
if (dialog && typeof dialog.showModal === 'function' && galleryLinks.length) {
  const picture = dialog.querySelector('img');
  const caption = dialog.querySelector('.lightbox-caption');
  const download = dialog.querySelector('[data-original]');
  const counter = dialog.querySelector('[data-image-count]');
  let index = 0;
  let opener = null;
  function display(next) {
    index = (next + galleryLinks.length) % galleryLinks.length;
    const link = galleryLinks[index];
    picture.src = link.href;
    picture.alt = link.dataset.caption || link.querySelector('img')?.alt || 'Project image';
    caption.textContent = picture.alt;
    download.href = link.href;
    counter.textContent = `${index + 1} / ${galleryLinks.length}`;
  }
  galleryLinks.forEach((link, position) => link.addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    opener = link;
    display(position);
    dialog.showModal();
    document.documentElement.classList.add('lightbox-open');
  }));
  dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
  dialog.querySelector('[data-previous]').addEventListener('click', () => display(index - 1));
  dialog.querySelector('[data-next]').addEventListener('click', () => display(index + 1));
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') { event.preventDefault(); display(index - 1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); display(index + 1); }
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('lightbox-open');
    picture.removeAttribute('src');
    opener?.focus();
  });
  if (galleryLinks.length === 1) {
    dialog.querySelector('[data-previous]').hidden = true;
    dialog.querySelector('[data-next]').hidden = true;
  }
}

const contact = document.querySelector('#contact-form');
if (contact) {
  contact.removeAttribute('hidden');
  contact.addEventListener('submit', event => {
    event.preventDefault();
    if (!contact.reportValidity()) return;
    const data = new FormData(contact);
    const name = String(data.get('name') || '').trim();
    const email = String(data.get('email') || '').trim();
    const subject = String(data.get('subject') || 'Portfolio inquiry').trim();
    const message = String(data.get('message') || '').trim();
    const body = `${message}\n\nFrom: ${name}\nReply to: ${email}`;
    const href = `mailto:${contact.dataset.recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    document.querySelector('#contact-status').textContent = 'Opening your email app. Review your message there and send it. If no app opens, use the email address above.';
    window.location.href = href;
  });
}

// Respect motion preferences before starting optional animated demonstrations.
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const animations = document.querySelectorAll('video[data-animated]');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.play().catch(() => {});
        else entry.target.pause();
      });
    }, { threshold: 0.15 });
    animations.forEach(video => observer.observe(video));
  }
}
