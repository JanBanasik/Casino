import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(username, email, password);
      navigate("/konto");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejestracja nie powiodła się");
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
          placeholder="min. 3 znaki"
          minLength={3}
          required
        />
      </label>
      <label className="field">
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jan@example.com"
          required
        />
      </label>
      <label className="field">
        <span>Hasło</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="min. 8 znaków"
          minLength={8}
          required
        />
      </label>
      {error && <p className="form-error">{error}</p>}
      <button type="submit" className="btn btn-gold btn-block btn-lg" disabled={loading}>
        {loading ? "Tworzenie konta…" : "Utwórz konto"}
      </button>
      <p className="auth-switch">
        Masz już konto? <Link to="/login">Zaloguj się</Link>
      </p>
    </form>
  );
}
