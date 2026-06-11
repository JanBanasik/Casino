import { Link } from "react-router-dom";

export default function PromotionsPage() {
  return (
    <div className="container page">
      <div className="page-header">
        <h1>Promocje</h1>
        <p>Oferty specjalne i bonusy dla graczy.</p>
      </div>

      <div className="promo-grid">
        <article className="promo-tile promo-tile--gold">
          <span className="promo-tag">Powitalna</span>
          <h2>Bonus na start</h2>
          <p>
            Każde nowe konto zaczyna z pakietem żetonów na powitanie — wystarczy,
            by od razu spróbować wszystkich gier.
          </p>
        </article>
        <article className="promo-tile">
          <span className="promo-tag">Codziennie</span>
          <h2>Dzienny bonus</h2>
          <p>
            Wracaj codziennie po darmowe żetony. Im dłuższa seria logowań, tym
            większa nagroda. Odbierzesz ją w sekcji{" "}
            <Link to="/konto">„Konto”</Link>.
          </p>
        </article>
        <article className="promo-tile">
          <span className="promo-tag">Aktywna</span>
          <h2>Zwrot za pechową serię</h2>
          <p>
            Pech się zdarza — co 5 przegranych z rzędu oddajemy część postawionych
            stawek. Działa w blackjacku, pokerze i ruletce.
          </p>
        </article>
        <article className="promo-tile">
          <span className="promo-tag">Zawsze</span>
          <h2>Koło ratunkowe</h2>
          <p>
            Gdy żetony się skończą, automatycznie doładujemy konto, żebyś mógł grać
            dalej. Bez końca zabawy.
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
