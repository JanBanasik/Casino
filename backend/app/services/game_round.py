from __future__ import annotations

import random
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import GameSession, GameType, Round, RoundResult, TransactionType
from app.engine.blackjack import (
    BlackjackAction,
    BlackjackPhase,
    BlackjackState,
    apply_action,
    new_round_state,
    play_dealer,
    settle,
)
from app.schemas.table_state import RedisTableState, load_table_state, save_table_state
from app.services.retention import RetentionService
from app.services.wallet import WalletService


class GameRoundService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis

    async def _get_session_owned(self, session_id: UUID, user_id: UUID) -> GameSession | None:
        res = await self.session.execute(select(GameSession).where(GameSession.id == session_id))
        gs = res.scalar_one_or_none()
        if gs is None or gs.user_id != user_id:
            return None
        return gs

    async def new_round(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        bet: float,
    ) -> tuple[RedisTableState | None, dict]:
        gs = await self._get_session_owned(game_session_id, user_id)
        if gs is None:
            raise ValueError("session_not_found")
        if gs.game_type != GameType.blackjack:
            raise ValueError("unsupported_game")
        wallet_svc = WalletService(self.session)
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise ValueError("no_wallet")
        if wallet.balance < bet:
            raise ValueError("insufficient_balance")

        await wallet_svc.apply_amount(wallet.id, -bet, TransactionType.bet)
        st = new_round_state(bet=bet, rng=random.Random())

        if st.phase == BlackjackPhase.finished:
            bonus = await self._finalize_round_db(
                st,
                game_session_id,
                user_id,
                table_id,
                wallet_svc,
            )
            await self.session.commit()
            public = st.to_public_dict()
            if bonus:
                public["retention"] = bonus
            return None, public

        redis_st = RedisTableState.from_blackjack(table_id, game_session_id, user_id, st)
        await save_table_state(self.redis, redis_st, settings.table_state_ttl_seconds)
        await self.session.commit()
        return redis_st, st.to_public_dict()

    async def apply_player_action(
        self,
        user_id: UUID,
        table_id: str,
        action: BlackjackAction,
    ) -> dict:
        loaded = await load_table_state(self.redis, table_id)
        if loaded is None:
            raise ValueError("no_active_round")
        if loaded.user_id != user_id:
            raise ValueError("forbidden")

        st = loaded.to_blackjack()
        if st.phase == BlackjackPhase.finished:
            return {"public": st.to_public_dict(), "retention": None}

        wallet_svc = WalletService(self.session)
        if st.phase == BlackjackPhase.player_turn:
            apply_action(st, action)
            if st.phase == BlackjackPhase.dealer_turn:
                play_dealer(st)

        bonus_meta: dict | None = None
        if st.phase == BlackjackPhase.finished:
            bonus_meta = await self._finalize_round_db(
                st, loaded.session_id, user_id, table_id, wallet_svc
            )
            await self.redis.delete(f"table:{table_id}:state")
            await self.session.commit()
            out = st.to_public_dict()
            if bonus_meta:
                out["retention"] = bonus_meta
            return {"public": out, "retention": bonus_meta}

        await save_table_state(
            self.redis,
            RedisTableState.from_blackjack(table_id, loaded.session_id, user_id, st),
            settings.table_state_ttl_seconds,
        )
        await self.session.commit()
        return {"public": st.to_public_dict(), "retention": None}

    async def _finalize_round_db(
        self,
        st: BlackjackState,
        session_id: UUID,
        user_id: UUID,
        table_id: str,
        wallet_svc: WalletService,
    ) -> dict | None:
        result_key, credit = settle(st)
        rr = RoundResult[result_key] if result_key in RoundResult.__members__ else RoundResult.draw
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise ValueError("no_wallet")
        if credit > 0:
            await wallet_svc.apply_amount(wallet.id, credit, TransactionType.win)

        self.session.add(
            Round(
                session_id=session_id,
                result=rr,
                payout_amount=credit,
                ai_actions={"dealer_policy": "rules_mvp", "table_id": table_id},
            )
        )
        await self.session.flush()

        if rr != RoundResult.loss:
            return None

        ret = RetentionService(self.session)
        granted, amount = await ret.maybe_bad_beat_bonus(user_id, wallet_svc)
        if granted:
            return {"bad_beat_bonus": True, "amount": amount}
        return None
