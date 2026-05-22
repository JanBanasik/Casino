export default function PromotionsPage() {
  return (
    <div className="container page">
      <div className="page-header">
        <h1>Promocje</h1>
        <p>Oferty specjalne i bonusy dla graczy.</p>
      </div>

      <div className="promo-grid">
        <article className="promo-tile promo-tile--gold">
          <span className="promo-tag">Aktywna</span>
          <h2>Bonus passy</h2>
          <p>
            Czasem pechowa seria to tylko początek szczęśliwej passy. Graj dalej —
            niespodzianki czekają przy stole.
          </p>
        </article>
        <article className="promo-tile">
          <span className="promo-tag">Powitalna</span>
          <h2>Pierwsze żetony</h2>
          <p>
            Doładuj portfel w sekcji „Konto” i usiądź przy wybranym stole na żywo.
          </p>
        </article>
        <article className="promo-tile promo-tile--muted">
          <span className="promo-tag">Wkrótce</span>
          <h2>Turnieje stołowe</h2>
          <p>
            Rywalizacja wielu graczy przy jednym stole z rankingiem — już wkrótce.
          </p>
        </article>
      </div>
    </div>
  );
}
