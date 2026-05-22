import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/stoły";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate(from);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logowanie nie powiodło się");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="auth-form">
      <label className="field">
        <span>Nazwa użytkownika</span>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="twoj_login"
          autoComplete="username"
          required
        />
      </label>
      <label className="field">
        <span>Hasło</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          autoComplete="current-password"
          required
        />
      </label>
      {error && <p className="form-error">{error}</p>}
      <button type="submit" className="btn btn-gold btn-block btn-lg" disabled={loading}>
        {loading ? "Logowanie…" : "Zaloguj się"}
      </button>
      <p className="auth-switch">
        Nie masz konta? <Link to="/register">Zarejestruj się</Link>
      </p>
    </form>
  );
}
