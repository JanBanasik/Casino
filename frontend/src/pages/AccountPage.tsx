import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useDailyBonus, formatCountdown } from "../hooks/useDailyBonus";
import {
  buyChips,
  claimRescue,
  getHistory,
  getPaymentConfig,
  getWallet,
  withdrawChips,
} from "../services/api";
import type { PaymentConfigResponse, RoundHistoryItem } from "../types/api";

const CHIP_PACKS = [250, 500, 1000, 2500, 5000];

const GAME_LABELS: Record<string, string> = {
  blackjack: "Blackjack",
  poker: "Poker",
  roulette: "Ruletka",
};

const RESULT_LABELS: Record<string, string> = {
  win: "Wygrana",
  loss: "Przegrana",
  draw: "Remis",
};

function chipsToPln(chips: number, rate: number): number {
  return rate > 0 ? chips / rate : 0;
}

export default function AccountPage() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [history, setHistory] = useState<RoundHistoryItem[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const { status: daily, claimable: dailyClaimable, secondsLeft: dailySeconds, claim: claimDailyBonus } =
    useDailyBonus();
  const [payCfg, setPayCfg] = useState<PaymentConfigResponse | null>(null);
  const [buyPack, setBuyPack] = useState(CHIP_PACKS[1]);
  const [withdrawAmount, setWithdrawAmount] = useState(0);
  const [accountNumber, setAccountNumber] = useState("");

  const rate = payCfg?.chips_per_currency_unit ?? 5;
  const currency = (payCfg?.currency ?? "pln").toUpperCase();

  const refresh = useCallback(async () => {
    const [w, h] = await Promise.all([
      getWallet().catch(() => null),
      getHistory(20).catch(() => null),
    ]);
    if (w) setBalance(w.balance);
    if (h) setHistory(h.rounds);
  }, []);

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    getPaymentConfig().then(setPayCfg).catch(() => undefined);
    refresh()
      .catch((e) => setError(e instanceof Error ? e.message : "Błąd ładowania"))
      .finally(() => setLoading(false));
  }, [token, navigate, refresh]);

  // Handle return from Stripe Checkout.
  useEffect(() => {
    const purchase = searchParams.get("purchase");
    if (!purchase) return;
    if (purchase === "success") {
      setSuccess("Płatność zakończona — żetony zostaną dopisane po potwierdzeniu.");
      refresh().catch(() => undefined);
    } else if (purchase === "cancel") {
      setError("Płatność anulowana.");
    }
    searchParams.delete("purchase");
    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams, refresh]);

  async function onBuy() {
    setError(null);
    setSuccess(null);
    setBusy("buy");
    try {
      const res = await buyChips(buyPack);
      if (res.url) {
        window.location.href = res.url; // redirect to Stripe Checkout
        return;
      }
      if (res.balance != null) setBalance(res.balance);
      setSuccess(
        `Kupiono ${buyPack.toLocaleString("pl-PL")} żetonów za ` +
          `${(res.amount_minor / 100).toFixed(2)} ${res.currency.toUpperCase()}.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Zakup nie powiódł się");
    } finally {
      setBusy(null);
    }
  }

  async function onWithdraw() {
    setError(null);
    setSuccess(null);
    setBusy("withdraw");
    try {
      const res = await withdrawChips(withdrawAmount, accountNumber);
      setBalance(res.balance);
      setSuccess(
        `Zlecono wypłatę ${res.chips.toLocaleString("pl-PL")} żetonów ` +
          `(${(res.amount_minor / 100).toFixed(2)} ${res.currency.toUpperCase()}).`,
      );
      await refresh();
    } catch (err) {
      setError(mapPayError(err instanceof Error ? err.message : "Wypłata nie powiodła się"));
    } finally {
      setBusy(null);
    }
  }

  async function onClaimDaily() {
    setError(null);
    setSuccess(null);
    setBusy("daily");
    try {
      const res = await claimDailyBonus();
      if (res.granted) {
        setBalance(res.balance);
        setSuccess(`Odebrano dzienny bonus: +${Math.round(res.amount)} Ż (seria ${res.streak ?? 1})`);
      } else {
        setError("Dzienny bonus już odebrany — wróć później.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się odebrać bonusu");
    } finally {
      setBusy(null);
    }
  }

  async function onClaimRescue() {
    setError(null);
    setSuccess(null);
    setBusy("rescue");
    try {
      const res = await claimRescue();
      if (res.granted) {
        setBalance(res.balance);
        setSuccess(`Koło ratunkowe: +${Math.round(res.amount)} Ż`);
      } else {
        setError("Koło ratunkowe niedostępne — saldo nie jest jeszcze na zerze.");
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Koło ratunkowe niedostępne");
    } finally {
      setBusy(null);
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
        <p>Portfel, bonusy i historia gier.</p>
      </div>

      {success && <div className="banner banner--info">{success}</div>}
      {error && <div className="banner banner--error">{error}</div>}

      <div className="account-grid">
        <section className="account-card account-card--balance">
          <span className="account-label">Saldo</span>
          <p className="account-balance">{balance.toLocaleString("pl-PL")} <small>Ż</small></p>
          {balance < 10 && (
            <button
              type="button"
              className="btn btn-gold btn-sm"
              disabled={busy === "rescue"}
              onClick={onClaimRescue}
            >
              {busy === "rescue" ? "…" : "Odbierz koło ratunkowe"}
            </button>
          )}
        </section>

        <section className="account-card account-card--daily">
          <h2>Dzienny bonus</h2>
          <p className="account-daily-streak">
            Seria logowań: <strong>{daily?.streak ?? 0}</strong> dni
          </p>
          {dailyClaimable ? (
            <p className="account-daily-amount">
              Do odebrania: +{Math.round(daily?.next_amount ?? 0).toLocaleString("pl-PL")} Ż
            </p>
          ) : (
            <p className="account-daily-amount account-daily-amount--wait">
              Następny bonus za{" "}
              <strong className="daily-timer">{formatCountdown(dailySeconds)}</strong>
            </p>
          )}
          <button
            type="button"
            className="btn btn-gold btn-block"
            disabled={!dailyClaimable || busy === "daily"}
            onClick={onClaimDaily}
          >
            {busy === "daily" ? "Odbieranie…" : dailyClaimable ? "Odbierz bonus" : "Niedostępne"}
          </button>
        </section>

        <section className="account-card">
          <h2>Kup żetony</h2>
          <p className="pay-rate-note">
            Kurs: 1 {currency} = {rate} Ż &middot; 1 żeton = {chipsToPln(1, rate).toFixed(2)} {currency}
          </p>
          <div className="chip-presets">
            {CHIP_PACKS.map((n) => (
              <button
                key={n}
                type="button"
                className={`casino-chip ${buyPack === n ? "casino-chip--active" : ""}`}
                onClick={() => setBuyPack(n)}
              >
                {n}
              </button>
            ))}
          </div>
          <div className="pay-summary">
            {buyPack.toLocaleString("pl-PL")} Ż za{" "}
            <strong>{chipsToPln(buyPack, rate).toFixed(2)} {currency}</strong>
          </div>
          <button
            type="button"
            className="btn btn-gold btn-block"
            disabled={busy === "buy"}
            onClick={onBuy}
          >
            {busy === "buy" ? "Przekierowanie…" : "Zapłać kartą"}
          </button>
        </section>

        <section className="account-card">
          <h2>Wypłać środki</h2>
          <p className="pay-rate-note">
            Minimalna wypłata: {(payCfg?.withdraw_min_chips ?? 250).toLocaleString("pl-PL")} Ż
          </p>
          <label className="field">
            <span>Żetony do wypłaty</span>
            <input
              type="number"
              min={0}
              max={balance}
              value={withdrawAmount}
              onChange={(e) => setWithdrawAmount(Number(e.target.value))}
            />
          </label>
          <label className="field">
            <span>Numer konta (IBAN)</span>
            <input
              type="text"
              inputMode="numeric"
              placeholder="PL00 0000 0000 0000 0000 0000 0000"
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
            />
          </label>
          <div className="pay-summary">
            Otrzymasz <strong>{chipsToPln(withdrawAmount, rate).toFixed(2)} {currency}</strong>
          </div>
          <button
            type="button"
            className="btn btn-outline-gold btn-block"
            disabled={
              busy === "withdraw" ||
              withdrawAmount < (payCfg?.withdraw_min_chips ?? 250) ||
              withdrawAmount > balance ||
              accountNumber.replace(/\s/g, "").length < 10
            }
            onClick={onWithdraw}
          >
            {busy === "withdraw" ? "Przetwarzanie…" : "Wypłać na konto"}
          </button>
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

      <section className="account-card account-card--history">
        <h2>Historia rozdań</h2>
        {history.length === 0 ? (
          <p className="account-history-empty">Brak rozegranych rund. Czas zagrać!</p>
        ) : (
          <table className="account-history-table">
            <thead>
              <tr>
                <th>Gra</th>
                <th>Wynik</th>
                <th>Zakład</th>
                <th>Wypłata</th>
                <th>Bilans</th>
                <th>Kiedy</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r) => (
                <tr key={r.id}>
                  <td>{GAME_LABELS[r.game_type] ?? r.game_type}</td>
                  <td>
                    <span className={`history-result history-result--${r.result}`}>
                      {RESULT_LABELS[r.result] ?? r.result}
                    </span>
                  </td>
                  <td>{Math.round(r.bet_amount).toLocaleString("pl-PL")} Ż</td>
                  <td>{Math.round(r.payout_amount).toLocaleString("pl-PL")} Ż</td>
                  <td className={r.net >= 0 ? "history-net--pos" : "history-net--neg"}>
                    {r.net >= 0 ? "+" : "−"}{Math.abs(Math.round(r.net)).toLocaleString("pl-PL")} Ż
                  </td>
                  <td>{new Date(r.created_at).toLocaleString("pl-PL")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function mapPayError(code: string): string {
  const map: Record<string, string> = {
    below_min_withdrawal: "Kwota poniżej minimalnej wypłaty.",
    insufficient_balance: "Niewystarczające saldo na wypłatę.",
    no_wallet: "Brak portfela.",
    amount_too_small: "Kwota zbyt mała.",
    invalid_account_number: "Nieprawidłowy numer konta (IBAN).",
  };
  return map[code] ?? code;
}
