import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { placeTourCard, tourSteps, type TourRect, type TourSession } from "../lib/productTour";
import { ShellIcon } from "./TerminalShellUi";
import "./product-tour.css";

type Anchor = { id: string; rect: TourRect };
const viewport = () => ({ width: window.innerWidth, height: window.innerHeight });
const routeOf = (path: string) => path.split("?")[0];

function visibleRect(element: HTMLElement): TourRect | null {
  const rect = element.getBoundingClientRect();
  let left = Math.max(0, rect.left - 5);
  let top = Math.max(0, rect.top - 5);
  let right = Math.min(window.innerWidth, rect.right + 5);
  let bottom = Math.min(window.innerHeight, rect.bottom + 5);
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    const { overflowX, overflowY } = getComputedStyle(parent);
    if (overflowX === "visible" && overflowY === "visible") continue;
    const bounds = parent.getBoundingClientRect();
    if (overflowX !== "visible") { left = Math.max(left, bounds.left); right = Math.min(right, bounds.right); }
    if (overflowY !== "visible") { top = Math.max(top, bounds.top); bottom = Math.min(bottom, bounds.bottom); }
  }
  return right - left > 4 && bottom - top > 4 ? { left, top, width: right - left, height: bottom - top } : null;
}

function useTourAnchor(targets: string[], onStepPage: boolean, routeKey: string) {
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const [screen, setScreen] = useState(viewport);
  const [lastRect, setLastRect] = useState<TourRect | null>(null);
  const target = useRef<HTMLElement>();

  useLayoutEffect(() => {
    let frame = 0;
    let preferred: HTMLElement | undefined;
    const resize = new ResizeObserver(queue);
    target.current = undefined;

    function measure() {
      frame = 0;
      const nextScreen = viewport();
      setScreen(previous => previous.width === nextScreen.width && previous.height === nextScreen.height ? previous : nextScreen);
      const candidates = onStepPage ? targets.flatMap(id => Array.from(document.querySelectorAll<HTMLElement>(
        '[data-tour-target="' + id + '"]:not(:disabled)')).filter(element => element.getClientRects().length)) : [];
      const primary = candidates[0];
      if (primary !== preferred) {
        if (preferred) resize.unobserve(preferred);
        preferred = primary;
        if (primary) {
          resize.observe(primary);
          if (!visibleRect(primary)) primary.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
        }
      }
      const next = candidates.find(element => visibleRect(element));
      const rect = next ? visibleRect(next) : null;
      target.current = next;
      const id = next?.dataset.tourTarget;
      if (rect && id) {
        setAnchor(previous => previous?.id === id && Object.keys(rect).every(key =>
          Math.abs(rect[key as keyof TourRect] - previous.rect[key as keyof TourRect]) < .5) ? previous : { id, rect });
        setLastRect(previous => previous?.left === rect.left && previous.top === rect.top &&
          previous.width === rect.width && previous.height === rect.height ? previous : rect);
      } else setAnchor(null);
    }

    function queue() {
      if (!frame) frame = requestAnimationFrame(measure);
    }

    const main = document.querySelector(".terminal-main");
    const mutations = new MutationObserver(queue);
    if (main) {
      resize.observe(main);
      mutations.observe(main, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "hidden"] });
    }
    window.addEventListener("resize", queue);
    window.addEventListener("scroll", queue, true);
    main?.addEventListener("animationend", queue, true);
    measure();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      mutations.disconnect();
      window.removeEventListener("resize", queue);
      window.removeEventListener("scroll", queue, true);
      main?.removeEventListener("animationend", queue, true);
    };
  }, [targets, onStepPage, routeKey]);

  return { anchor, lastRect, screen, target };
}

export default function ProductTour({ session, close }: { session: TourSession; close: (stepId: string) => void }) {
  const [room, setRoom] = useState(session.room);
  const steps = useMemo(() => tourSteps({ ...session, room }), [session, room]);
  const [index, setIndex] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [routeLeaving, setRouteLeaving] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const step = steps[index];
  const { anchor, lastRect, screen, target } = useTourAnchor(step.targets, location.pathname === routeOf(step.path), location.key);
  const titleId = useId();
  const descriptionId = useId();
  const maskId = useId();
  const title = useRef<HTMLHeadingElement>(null);
  const popup = useRef<HTMLElement>(null);
  const timer = useRef<number>();
  const [size, setSize] = useState({ width: 342, height: 225 });
  useEffect(() => {
    if ((step.id === "team" || (step.path === room && room === "/workspace")) && /^\/runs\/[^/]+$/.test(location.pathname)) {
      setRoom(location.pathname + location.search);
    }
  }, [step.id, step.path, room, location.pathname, location.search]);

  useLayoutEffect(() => {
    const element = popup.current;
    if (!element) return;
    const measure = () => setSize(previous => previous.width === element.offsetWidth && previous.height === element.offsetHeight
      ? previous : { width: element.offsetWidth, height: element.offsetHeight });
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    title.current?.focus({ preventScroll: true });
  }, [index]);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape" && !event.defaultPrevented && !document.querySelector("dialog[open]")) close(step.id);
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [close, step.id]);

  function move(next: number) {
    if (timer.current !== undefined) return;
    if (next >= steps.length) { close(step.id); return; }
    const destination = steps[next].path;
    const changesPage = location.pathname !== routeOf(destination);
    function finish() {
      timer.current = undefined;
      if (changesPage) navigate(destination);
      setIndex(next);
      setLeaving(false);
      setRouteLeaving(false);
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { finish(); return; }
    setLeaving(true);
    setRouteLeaving(changesPage);
    timer.current = window.setTimeout(finish, 140);
  }

  const element = target.current;
  const control = element?.matches("a,button,select,input") ? element :
    element?.querySelector<HTMLElement>("[data-tour-primary]") ?? element?.querySelector<HTMLElement>("a,button:not(:disabled),select,input");
  const position = placeTourCard(anchor?.rect ?? null, screen, size);
  const hint = anchor && step.hints?.[anchor.id];
  const sideArrow = position.side === "left" || position.side === "right";
  const arrow = anchor && (sideArrow
    ? anchor.rect.top + anchor.rect.height / 2 - position.top
    : anchor.rect.left + anchor.rect.width / 2 - position.left);
  const limit = sideArrow ? size.height : size.width;
  const highlight = lastRect && {
    width: lastRect.width, height: lastRect.height, transform: "translate(" + lastRect.left + "px," + lastRect.top + "px)",
  };
  return <div className="product-tour" data-step={step.id} data-leaving={leaving} data-route-leaving={routeLeaving}>
    <svg className="product-tour-shade" width="100%" height="100%" aria-hidden="true">
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="100%" height="100%">
          <rect width="100%" height="100%" fill="white" />
          {highlight && <rect className="product-tour-cutout" rx="11" fill="black" data-visible={Boolean(anchor)} style={highlight} />}
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="#060910" fillOpacity=".21" mask={"url(#" + maskId + ")"} />
    </svg>
    {highlight && <div className="product-tour-spotlight" aria-hidden="true" data-visible={Boolean(anchor)} style={highlight} />}
    <div className="product-tour-position" style={{
      transform: "translate(" + position.left + "px," + position.top + "px)",
      "--tour-arrow": Math.max(22, Math.min(arrow ?? 40, limit - 22)) + "px",
    } as CSSProperties}>
      <section className="product-tour-card" ref={popup} data-side={position.side} role="dialog" aria-labelledby={titleId} aria-describedby={descriptionId}>
        <div className="product-tour-content" key={step.id}>
          <div className="product-tour-top">
            <span className="product-tour-icon"><ShellIcon name={step.icon} /></span>
            <button type="button" className="product-tour-close" onClick={() => close(step.id)} aria-label="Close guided tour"><ShellIcon name="close" /></button>
          </div>
          <h2 ref={title} tabIndex={-1} id={titleId}>{step.title}</h2>
          <p id={descriptionId}>{step.body}</p>
          {hint && <p className="product-tour-hint">{hint}</p>}
          <footer>
            <span className="product-tour-count">{index + 1} of {steps.length}</span>
            {index > 0 && <button type="button" className="product-tour-secondary" disabled={leaving} onClick={() => move(index - 1)}>Back</button>}
            {index < steps.length - 1 && <button type="button" className="product-tour-secondary" disabled={leaving} onClick={() => move(index + 1)}>Skip step</button>}
            <button type="button" className="product-tour-next" disabled={leaving} onClick={() => move(index + 1)}>
              {step.id === "finish" ? (session.mode === "historical" ? "Keep exploring" : "Done") : "Next"}
            </button>
          </footer>
          {anchor && control && step.id !== "finish" && <button type="button" className="product-tour-focus"
            onClick={() => control.focus({ preventScroll: true })}>Focus highlighted control</button>}
        </div>
      </section>
    </div>
  </div>;
}
