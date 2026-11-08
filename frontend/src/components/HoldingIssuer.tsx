import ishares from "../assets/ishares.svg";
import vanguard from "../assets/vanguard.ico";

export default function HoldingIssuer({ name, ticker }: { name: string; ticker: string }) {
  const issuer = name.startsWith("iShares") ? ishares : name.startsWith("Vanguard") ? vanguard : undefined;
  return <span className="holding-issuer" aria-hidden="true">
    {issuer ? <img src={issuer} alt="" draggable={false} /> : ticker.slice(0, 2)}
  </span>;
}
