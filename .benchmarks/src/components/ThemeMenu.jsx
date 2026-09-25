import { useEffect, useRef, useState } from "react";
import { themeChoices } from "../theme";

export function ThemeMenu({ choice, onChange }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = (event) => {
      if (!root.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="theme-menu" ref={root}>
      {open && (
        <div className="theme-menu-panel" role="menu" aria-label="Tema">
          {themeChoices.map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="menuitemradio"
              aria-checked={choice === value}
              onClick={() => {
                onChange(value);
                setOpen(false);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <button
        className="theme-menu-button"
        type="button"
        aria-label="Cambiar tema"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}
