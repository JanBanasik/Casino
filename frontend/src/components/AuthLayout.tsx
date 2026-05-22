import { Link, Outlet } from "react-router-dom";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
}

export default function AuthLayout({ title, subtitle }: AuthLayoutProps) {
  return (
    <div className="auth-page">
      <div className="auth-visual">
        <div className="auth-visual-content">
          <Link to="/" className="brand brand--light">
            <span className="brand-icon">♠</span>
            Inteligentne Kasyno
          </Link>
          <h1>Wejdź do gry.<br />Poczuj emocje stołu.</h1>
          <p>
            Blackjack na żywo, pełne stoły z innymi graczami i krupierem —
            albo gra solo, kiedy chcesz.
          </p>
          <ul className="auth-features">
            <li>Stoły na żywo z krupierem</li>
            <li>Blackjack — więcej gier wkrótce</li>
            <li>Niespodzianki i bonusy lojalnościowe</li>
          </ul>
        </div>
        <div className="auth-visual-glow" />
      </div>
      <div className="auth-panel">
        <div className="auth-panel-inner">
          <h2>{title}</h2>
          <p className="auth-subtitle">{subtitle}</p>
          <Outlet />
          <p className="auth-back">
            <Link to="/">← Wróć na stronę główną</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
