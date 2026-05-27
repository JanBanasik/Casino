import GameCard from "../components/GameCard";
import { GAMES } from "../data/games";

export default function GamesPage() {
  const live = GAMES.filter((g) => g.available && g.category === "live");
  const cards = GAMES.filter((g) => g.available && g.category === "cards");
  const upcoming = GAMES.filter((g) => !g.available);

  return (
    <div className="container page">
      <div className="page-header">
        <h1>Gry</h1>
        <p>Wybierz grę i dołącz do stołu na żywo. Więcej tytułów w trakcie rozwoju projektu.</p>
      </div>

      <section className="page-section">
        <h2 className="page-section-title">Na żywo</h2>
        <div className="game-grid">
          {live.map((g) => (
            <GameCard key={g.id} game={g} />
          ))}
        </div>
      </section>

      {cards.length > 0 && (
        <section className="page-section">
          <h2 className="page-section-title">Karty</h2>
          <div className="game-grid">
            {cards.map((g) => (
              <GameCard key={g.id} game={g} />
            ))}
          </div>
        </section>
      )}

      {upcoming.length > 0 && (
        <section className="page-section">
          <h2 className="page-section-title">Wkrótce</h2>
          <div className="game-grid">
            {upcoming.map((g) => (
              <GameCard key={g.id} game={g} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
