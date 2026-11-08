import { useEffect, useRef, useState } from "react";
import "./panel-grip.css";

type Drag = { pointer: number; position: number; size: number; max: number };

export default function PanelGrip({ edge, panel, neighbor, variable, min, remaining, label, onResize }: {
  edge: "left" | "right" | "bottom"; panel: string; neighbor: string; variable: string; min: number; remaining: number;
  label: string; onResize?: () => void;
}) {
  const handle = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag>();
  const [value, setValue] = useState({ size: min, max: min });
  const [grabbing, setGrabbing] = useState(false);
  const vertical = edge === "bottom";
  const dimension = vertical ? "offsetHeight" : "offsetWidth";

  function measure() {
    const layout = handle.current?.parentElement;
    const target = layout?.querySelector<HTMLElement>(panel);
    const other = layout?.querySelector<HTMLElement>(neighbor);
    if (!layout || !target || !other) return;
    const size = target[dimension];
    const max = Math.max(min, size + other[dimension] - remaining);
    return { layout, target, other, size, max };
  }

  useEffect(() => {
    const initial = measure();
    if (!initial) return;
    const observer = new ResizeObserver(() => {
      const next = measure();
      if (next) setValue(current => current.size === next.size && current.max === next.max
        ? current : { size: next.size, max: next.max });
    });
    observer.observe(initial.layout);
    observer.observe(initial.target);
    observer.observe(initial.other);
    return () => observer.disconnect();
  // The measuring inputs are the supplied panel configuration.
  }, [panel, neighbor, edge, min, remaining]);

  function resize(size: number, max: number) {
    onResize?.();
    handle.current?.parentElement?.style.setProperty(variable, Math.round(Math.max(min, Math.min(max, size))) + "px");
  }

  function release() {
    drag.current = undefined;
    setGrabbing(false);
  }

  function reset() {
    onResize?.();
    handle.current?.parentElement?.style.removeProperty(variable);
  }

  return <div ref={handle} className="panel-grip" data-edge={edge} data-grabbing={grabbing || undefined}
    role="separator" tabIndex={0} aria-label={label} aria-orientation={vertical ? "horizontal" : "vertical"}
    aria-valuemin={min} aria-valuemax={Math.max(value.max, value.size)} aria-valuenow={Math.max(value.size, min)}
    title={label + " · Double-click or press Enter to reset"}
    onPointerDown={event => {
      if (event.button !== 0 || !event.isPrimary) return;
      const current = measure();
      if (!current) return;
      event.preventDefault();
      event.currentTarget.focus({ preventScroll: true });
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = { pointer: event.pointerId, position: vertical ? event.clientY : event.clientX, size: current.size, max: current.max };
      setGrabbing(true);
    }}
    onPointerMove={event => {
      const start = drag.current;
      if (!start || start.pointer !== event.pointerId) return;
      const distance = (vertical ? event.clientY : event.clientX) - start.position;
      resize(start.size + distance * (edge === "right" ? -1 : 1), start.max);
    }}
    onLostPointerCapture={release}
    onDoubleClick={reset}
    onKeyDown={event => {
      const current = measure();
      if (!current) return;
      const step = event.shiftKey ? 32 : 12;
      const forward = vertical ? "ArrowDown" : "ArrowRight";
      const backward = vertical ? "ArrowUp" : "ArrowLeft";
      if (event.key === "Enter") reset();
      else if (event.key === "Home") resize(min, current.max);
      else if (event.key === "End") resize(current.max, current.max);
      else if (event.key === forward || event.key === backward) {
        resize(current.size + step * (event.key === forward ? 1 : -1) * (edge === "right" ? -1 : 1), current.max);
      } else return;
      event.preventDefault();
    }}>
    <span aria-hidden="true"><i /><i /><i /></span>
  </div>;
}
