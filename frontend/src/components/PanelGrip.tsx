import { useEffect, useRef, useState } from "react";
import "./panel-grip.css";

type Drag = { pointer: number; position: number; size: number; max: number };

export default function PanelGrip({ edge, axis = "x", panel, variable, min, remaining, label, reverse = false, opposite }: {
  edge: string; axis?: "x" | "y"; panel: string; variable: string; min: number; remaining: number;
  label: string; reverse?: boolean; opposite?: string;
}) {
  const handle = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag>();
  const [value, setValue] = useState({ size: min, max: min });
  const [grabbing, setGrabbing] = useState(false);
  const dimension = axis === "x" ? "width" : "height";

  function measure() {
    const layout = handle.current?.parentElement;
    const target = layout?.querySelector<HTMLElement>(panel);
    if (!layout || !target) return;
    const total = axis === "x" ? layout.clientWidth : layout.clientHeight;
    const other = opposite ? layout.querySelector<HTMLElement>(opposite)?.getBoundingClientRect()[dimension] ?? 0 : 0;
    const max = Math.max(min, Math.floor(Math.min(total - remaining - other, axis === "x" ? total * .34 : total)));
    return { layout, target, size: Math.round(target.getBoundingClientRect()[dimension]), max };
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
    const other = opposite && initial.layout.querySelector(opposite);
    if (other) observer.observe(other);
    return () => observer.disconnect();
  // The measuring inputs are the supplied panel configuration.
  }, [panel, axis, min, remaining, opposite]);

  function resize(size: number, max: number) {
    handle.current?.parentElement?.style.setProperty(variable, Math.round(Math.max(min, Math.min(max, size))) + "px");
  }

  function release() {
    drag.current = undefined;
    setGrabbing(false);
  }

  return <div ref={handle} className="panel-grip" data-edge={edge} data-axis={axis} data-grabbing={grabbing || undefined}
    role="separator" tabIndex={0} aria-label={label} aria-orientation={axis === "x" ? "vertical" : "horizontal"}
    aria-valuemin={min} aria-valuemax={Math.max(value.max, value.size)} aria-valuenow={Math.max(value.size, min)}
    title={label + " · Double-click to reset"}
    onPointerDown={event => {
      if (event.button !== 0 || !event.isPrimary) return;
      const current = measure();
      if (!current) return;
      event.preventDefault();
      event.currentTarget.focus({ preventScroll: true });
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = { pointer: event.pointerId, position: axis === "x" ? event.clientX : event.clientY, size: current.size, max: current.max };
      setGrabbing(true);
    }}
    onPointerMove={event => {
      const start = drag.current;
      if (!start || start.pointer !== event.pointerId) return;
      const distance = (axis === "x" ? event.clientX : event.clientY) - start.position;
      resize(start.size + distance * (reverse ? -1 : 1), start.max);
    }}
    onLostPointerCapture={release}
    onDoubleClick={() => handle.current?.parentElement?.style.removeProperty(variable)}
    onKeyDown={event => {
      const current = measure();
      if (!current) return;
      const step = event.shiftKey ? 32 : 12;
      const forward = axis === "x" ? "ArrowRight" : "ArrowDown";
      const backward = axis === "x" ? "ArrowLeft" : "ArrowUp";
      if (event.key === "Home") resize(min, current.max);
      else if (event.key === "End") resize(current.max, current.max);
      else if (event.key === forward || event.key === backward) {
        resize(current.size + step * (event.key === forward ? 1 : -1) * (reverse ? -1 : 1), current.max);
      } else return;
      event.preventDefault();
    }}>
    <span aria-hidden="true"><i /><i /><i /></span>
  </div>;
}
