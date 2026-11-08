import { useEffect, useId, useRef, useState } from "react";
import "./finance-term.css";

export default function FinanceTerm({ name, help }: { name: string; help: string }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const tip = useRef<HTMLSpanElement>(null);
  const timer = useRef<number>();
  const [open, setOpen] = useState(false);
  const supported = typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;

  function show() {
    window.clearTimeout(timer.current);
    const anchor = button.current;
    const popup = tip.current;
    if (!supported || !anchor || !popup) return;
    if (!popup.matches(":popover-open")) popup.showPopover();
    const rect = anchor.getBoundingClientRect();
    const width = popup.offsetWidth;
    const height = popup.offsetHeight;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    const top = rect.bottom + height + 12 <= window.innerHeight ? rect.bottom + 5 : Math.max(8, rect.top - height - 5);
    popup.style.left = left + "px";
    popup.style.top = top + "px";
    setOpen(true);
  }

  function hide() {
    window.clearTimeout(timer.current);
    if (supported && tip.current?.matches(":popover-open")) tip.current.hidePopover();
    setOpen(false);
  }

  function hideSoon() {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(hide, 120);
  }

  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    if (!open) return;
    function dismiss(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      hide();
    }
    window.addEventListener("keydown", dismiss, true);
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("keydown", dismiss, true);
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [open]);

  return <span className="finance-term" onMouseEnter={show}
    onMouseLeave={() => { if (document.activeElement !== button.current) hideSoon(); }}>
    <span>{name}</span>
    <button ref={button} type="button" aria-label={"What does " + name + " mean?"} aria-describedby={id}
      title={supported ? undefined : help} onFocus={show} onBlur={hideSoon} onClick={show}>?</button>
    <span ref={tip} id={id} role="tooltip" className="finance-tip" {...{ popover: "manual" }}
      onMouseEnter={() => window.clearTimeout(timer.current)}
      onMouseLeave={() => { if (document.activeElement !== button.current) hideSoon(); }}>{help}</span>
  </span>;
}
