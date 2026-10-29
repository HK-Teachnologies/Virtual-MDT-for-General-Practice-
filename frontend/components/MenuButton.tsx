'use client';

export default function MenuButton() {
  function toggle() {
    document.body.classList.toggle('nav-open');
  }

  return (
    <button
      className="menu-btn"
      type="button"
      onClick={toggle}
      aria-label="Open navigation menu"
    >
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
    </button>
  );
}
