import { Link, NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { getWallet } from "../services/api";

export default function Navbar() {
  const { token, logout } = useAuth();
  const [balance, setBalance] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  // Refresh balance on login AND every 4 s during active session
  useEffect(() => {
    if (!token) {
      setBalance(null);
      return;
    }
    const refresh = () =>
      getWallet()
        .then((w) => setBalance(w.balance))
        .catch(() => setBalance(null));
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [token]);

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand">
          <span className="brand-icon">♠</span>
          <span className="brand-text">
            Inteligentne <strong>Kasyno</strong>
          </span>
        </Link>

        <button
          type="button"
          className="nav-toggle"
          aria-label="Menu"
          onClick={() => setMenuOpen((o) => !o)}
        >
          ☰
        </button>

        <nav className={`nav-links ${menuOpen ? "nav-links--open" : ""}`}>
          <NavLink to="/" end onClick={() => setMenuOpen(false)}>Strona główna</NavLink>
          <NavLink to="/gry" onClick={() => setMenuOpen(false)}>Gry</NavLink>
          <NavLink to="/stoły" onClick={() => setMenuOpen(false)}>Stoły na żywo</NavLink>
          <NavLink to="/roulette" onClick={() => setMenuOpen(false)}>Ruletka</NavLink>
          <NavLink to="/promocje" onClick={() => setMenuOpen(false)}>Promocje</NavLink>
        </nav>

        <div className="nav-actions">
          {token ? (
            <>
              <Link to="/konto" className="wallet-pill">
                <span className="wallet-icon">●</span>
                <span className="wallet-amount">
                  {balance !== null ? balance.toLocaleString("pl-PL") : "—"} Ż
                </span>
              </Link>
              <Link to="/konto" className="btn btn-ghost btn-sm">Konto</Link>
              <button type="button" className="btn btn-outline-gold btn-sm" onClick={logout}>
                Wyloguj
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost btn-sm">Zaloguj</Link>
              <Link to="/register" className="btn btn-gold btn-sm">Rejestracja</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
