import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { deposit, getWallet } from "../services/api";

export default function AccountPage() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [balance, setBalance] = useState(0);
  const [depositAmount, setDepositAmount] = useState(500);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    getWallet()
      .then((w) => setBalance(w.balance))
      .catch((e) => setError(e instanceof Error ? e.message : "Błąd ładowania"))
      .finally(() => setLoading(false));
  }, [token, navigate]);

  async function onDeposit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const w = await deposit(depositAmount);
      setBalance(w.balance);
      setSuccess(`Dodano ${depositAmount.toLocaleString("pl-PL")} żetonów`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Depozyt nie powiódł się");
    }
  }

  if (loading) {
    return (
      <div className="container page">
        <p className="loading-text">Ładowanie konta…</p>
      </div>
    );
  }

  return (
    <div className="container page">
      <div className="page-header">
        <h1>Moje konto</h1>
        <p>Portfel i szybki dostęp do gier.</p>
      </div>

      <div className="account-grid">
        <section className="account-card account-card--balance">
          <span className="account-label">Saldo</span>
          <p className="account-balance">{balance.toLocaleString("pl-PL")} <small>Ż</small></p>
        </section>

        <section className="account-card">
          <h2>Doładuj portfel</h2>
          <form onSubmit={onDeposit} className="deposit-form">
            <div className="chip-presets">
              {[100, 500, 1000, 5000].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`casino-chip ${depositAmount === n ? "casino-chip--active" : ""}`}
                  onClick={() => setDepositAmount(n)}
                >
                  {n}
                </button>
              ))}
            </div>
            <label className="field">
              <span>Kwota</span>
              <input
                type="number"
                min={1}
                value={depositAmount}
                onChange={(e) => setDepositAmount(Number(e.target.value))}
              />
            </label>
            <button type="submit" className="btn btn-gold btn-block">Doładuj konto</button>
          </form>
          {success && <p className="form-success">{success}</p>}
          {error && <p className="form-error">{error}</p>}
        </section>

        <section className="account-card">
          <h2>Szybkie akcje</h2>
          <div className="quick-actions">
            <Link to="/stoły" className="btn btn-gold btn-block">Stoły na żywo</Link>
            <Link to="/gry" className="btn btn-outline-gold btn-block">Katalog gier</Link>
            <button
              type="button"
              className="btn btn-ghost btn-block"
              onClick={() => { logout(); navigate("/"); }}
            >
              Wyloguj
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
