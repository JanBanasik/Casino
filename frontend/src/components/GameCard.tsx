import { Link } from "react-router-dom";
import type { GameInfo } from "../data/games";

interface GameCardProps {
  game: GameInfo;
}

export default function GameCard({ game }: GameCardProps) {
  const inner = (
    <>
      <div className="game-card-bg" style={{ background: game.imageGradient }} />
      <div className="game-card-body">
        <span className="game-card-badge">
          {game.category === "live" ? "NA ŻYWO" : game.available ? "KARTY" : "WKRÓTCE"}
        </span>
        <h3>{game.name}</h3>
        <p>{game.description}</p>
        <div className="game-card-meta">
          <span>Min. {game.minBet} Ż</span>
          {game.playersOnline > 0 && <span>{game.playersOnline} graczy online</span>}
        </div>
        {game.available ? (
          <span className="btn btn-gold btn-sm game-card-cta">Graj teraz</span>
        ) : (
          <span className="btn btn-disabled btn-sm game-card-cta">Wkrótce</span>
        )}
      </div>
    </>
  );

  if (game.available && game.route) {
    return (
      <Link to={game.route} className="game-card">
        {inner}
      </Link>
    );
  }

  return <article className="game-card game-card--disabled">{inner}</article>;
}
