import { useEffect, useRef, type HTMLAttributes } from "react";
import "./scroll-arrival.css";

export default function ScrollArrivalList({ children, ...props }: HTMLAttributes<HTMLUListElement>) {
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (!list.current || !("IntersectionObserver" in window) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const observer = new IntersectionObserver(entries => {
      for (const { isIntersecting, target } of entries) {
        if (!isIntersecting) continue;
        (target as HTMLElement).dataset.scrollArrived = "";
        observer.unobserve(target);
      }
    }, { threshold: .16 });
    for (const item of Array.from(list.current.children)) {
      if (!item.hasAttribute("data-scroll-arrived")) observer.observe(item);
    }
    return () => observer.disconnect();
  }, [children]);
  return <ul ref={list} {...props}>{children}</ul>;
}
