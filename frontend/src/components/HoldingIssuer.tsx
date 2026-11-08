import { useState } from "react";
import ishares from "../assets/ishares.svg";
import vanguard from "../assets/vanguard.ico";

const cachedImages = import.meta.glob<string>("../assets/holding-logos/*.{ico,png,svg}", {
  eager: true, query: "?url", import: "default",
});
const logos = new Map(Object.entries(cachedImages).map(([path, url]) =>
  [path.slice(path.lastIndexOf("/") + 1, path.lastIndexOf(".")), url]));

function IssuerImage({ images, initials }: { images: string[]; initials: string }) {
  const [index, setIndex] = useState(0);
  const src = images[index];
  return src ? <img src={src} alt="" draggable={false} decoding="async"
    onError={() => setIndex(index + 1)} /> : initials;
}

export default function HoldingIssuer({ name, ticker }: { name: string; ticker: string }) {
  const issuer = /^(ishares|vanguard)\b/i.exec(name)?.[0].toLowerCase();
  const primary = logos.get(ticker.toUpperCase()) ?? (issuer && logos.get(issuer));
  const fallback = issuer === "ishares" ? ishares : issuer === "vanguard" ? vanguard : undefined;
  const images = [...new Set([primary, fallback].filter((url): url is string => !!url))];
  return <span className="holding-issuer" aria-hidden="true">
    <IssuerImage key={ticker + ":" + (issuer ?? "")} images={images} initials={ticker.split(".")[0].slice(0, 2)} />
  </span>;
}
