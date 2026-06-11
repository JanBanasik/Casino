from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Inteligentne Kasyno API"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://casino:casino@localhost:15432/casino"
    redis_url: str = "redis://localhost:16379/0"

    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    table_state_ttl_seconds: int = 3600

    ws_ticket_ttl_seconds: int = 120
    ws_auth_timeout_seconds: int = 10

    # ── Bonus economy (play-money chips "Ż") ──────────────────────────────────
    # All values tuned against min bets of 5–100 Ż. Tweak freely without code
    # changes via env vars (e.g. BONUS_WELCOME=1500).
    bonus_welcome: float = 1000.0
    # Daily login reward: grows with the login streak from `daily` to `daily_max`.
    bonus_daily_base: float = 100.0
    bonus_daily_step: float = 50.0
    bonus_daily_max: float = 500.0
    bonus_daily_cooldown_hours: int = 20
    # Loss-streak ("bad beat"): refund a fraction of the last N lost stakes.
    bonus_loss_streak_count: int = 5
    bonus_loss_refund_pct: float = 0.5
    bonus_loss_refund_cap: float = 2000.0
    # Rescue: when the wallet can no longer cover a minimum bet, top it up.
    bonus_rescue_threshold: float = 10.0
    bonus_rescue_target: float = 200.0
    bonus_rescue_cooldown_minutes: int = 60

    # ── Payments (Stripe) ─────────────────────────────────────────────────────
    # Exchange rate: 1 unit of fiat buys this many chips. Default 5 ⇒ a chip is
    # worth 0.20 zł, i.e. one fiat unit equals the smallest stake in any game.
    chips_per_currency_unit: float = 5.0
    payment_currency: str = "pln"
    # Leave empty to run the app in "dev simulation" mode (no real charges).
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    # Where Stripe Checkout returns the player after pay / cancel.
    payment_success_url: str = "http://localhost:5173/konto?purchase=success"
    payment_cancel_url: str = "http://localhost:5173/konto?purchase=cancel"
    # Cash-out limits (in chips).
    withdraw_min_chips: float = 250.0

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)

    # Comma-separated list of allowed CORS origins (frontend URLs).
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
