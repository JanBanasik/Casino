import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import GameCard from "../components/GameCard";
import { GAMES, LIVE_TABLES } from "../data/games";

export default function HomePage() {
  const { token } = useAuth();
  const featured = GAMES.filter((g) => g.available).slice(0, 3);
  const livePreview = LIVE_TABLES.filter((t) => t.featured);

  return (
    <>
      <section className="hero">
        <div className="hero-bg" />
        <div className="container hero-content">
          <div className="hero-text">
            <span className="hero-tag">Kasyno na żywo</span>
            <h1>Poczuj klimat<br /><span className="gold-text">prawdziwego stołu</span></h1>
            <p>
              Blackjack na żywo z krupierem, pełne stoły z innymi graczami albo gra solo —
              wszystko w jednym miejscu.
            </p>
            <div className="hero-actions">
              <Link to="/stoły" className="btn btn-gold btn-lg">Wejdź do stołów na żywo</Link>
              {!token && (
                <Link to="/register" className="btn btn-outline-gold btn-lg">Załóż konto</Link>
              )}
            </div>
          </div>
          <div className="hero-promo">
            <div className="promo-card promo-card--main">
              <span className="promo-label">Oferta specjalna</span>
              <h3>Bonus passy</h3>
              <p>Pechowa seria? Czasem los się odwraca — sprawdź promocje.</p>
              <Link to="/promocje" className="promo-link">Szczegóły →</Link>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-header">
            <h2>Polecane gry</h2>
            <Link to="/gry" className="section-link">Zobacz wszystkie →</Link>
          </div>
          <div className="game-grid">
            {featured.map((g) => (
              <GameCard key={g.id} game={g} />
            ))}
          </div>
        </div>
      </section>

      <section className="section section--dark">
        <div className="container">
          <div className="section-header">
            <h2>Stoły na żywo</h2>
            <span className="live-indicator">
              <span className="live-dot" /> LIVE · {LIVE_TABLES.reduce((a, t) => a + t.seatsTaken, 0)} graczy online
            </span>
          </div>
          <div className="live-preview-grid">
            {livePreview.map((t) => (
              <div key={t.id} className="live-preview-card">
                <span className="live-badge live-badge--sm">LIVE</span>
                <h3>{t.name}</h3>
                <p>{t.dealerName}</p>
                <span>{t.seatsTaken}/{t.seatsTotal} graczy · od {t.minBet} Ż</span>
              </div>
            ))}
          </div>
          <div className="section-cta">
            <Link to="/stoły" className="btn btn-gold">Wybierz stół i graj</Link>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container trust-row">
          <div className="trust-item">
            <strong>Stoły 24/7</strong>
            <span>Gra solo lub wieloosobowa</span>
          </div>
          <div className="trust-item">
            <strong>Krupierzy na żywo</strong>
            <span>Prawdziwe tempo gry</span>
          </div>
          <div className="trust-item">
            <strong>Promocje</strong>
            <span>Bonusy i oferty specjalne</span>
          </div>
          <div className="trust-item">
            <strong>Bezpieczny portfel</strong>
            <span>Żetony zawsze pod ręką</span>
          </div>
        </div>
      </section>
    </>
  );
}
