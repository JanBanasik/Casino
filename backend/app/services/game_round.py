from __future__ import annotations

import random
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import GameSession, GameType, Round, RoundResult, TransactionType, User
from app.engine.blackjack import BlackjackAction, BlackjackPhase
from app.engine.multi_seat import (
    MultiSeatBlackjackState,
    advance_bot_turns,
    apply_seat_action,
    finish_dealer_and_settle,
    human_settle_result,
    new_multi_round,
)
from app.ml_inference.policies import BasicStrategyPolicy
from app.schemas.table_state import RedisTableState, load_table_state, save_table_state
from app.services.retention import RetentionService
from app.services.wallet import WalletService

_bot_policy = BasicStrategyPolicy()


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

    async def _username(self, user_id: UUID) -> str:
        res = await self.session.execute(select(User.username).where(User.id == user_id))
        row = res.scalar_one_or_none()
        return row or "Gracz"

    async def new_round(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        bet: float,
        *,
        solo: bool = False,
        bot_count: int = 0,
    ) -> tuple[RedisTableState | None, dict, list[dict]]:
        gs = await self._get_session_owned(game_session_id, user_id)
        if gs is None:
            raise ValueError("session_not_found")
        if gs.game_type != GameType.blackjack:
            raise ValueError("unsupported_game")

        if solo:
            bot_count = 0
        bot_count = max(0, min(bot_count, 6))

        wallet_svc = WalletService(self.session)
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise ValueError("no_wallet")
        if wallet.balance < bet:
            raise ValueError("insufficient_balance")

        await wallet_svc.apply_amount(wallet.id, -bet, TransactionType.bet)
        username = await self._username(user_id)

        st = new_multi_round(
            bet=bet,
            human_name=username,
            human_id=str(user_id),
            bot_count=bot_count,
            rng=random.Random(),
        )

        seat_events: list[dict] = []
        pre_human = advance_bot_turns(st, _bot_policy, stop_at_human=True)
        for idx, action in pre_human:
            seat_events.append({"seat_index": idx, "action": action.value, "display_name": st.seats[idx].display_name})

        if st.phase == BlackjackPhase.finished:
            finish_dealer_and_settle(st)
            bonus = await self._finalize_round_db(st, game_session_id, user_id, table_id, wallet_svc)
            await self.session.commit()
            public = st.to_public_dict()
            if bonus:
                public["retention"] = bonus
            return None, public, seat_events

        redis_st = RedisTableState.from_multi(table_id, game_session_id, user_id, st, bot_count)
        await save_table_state(self.redis, redis_st, settings.table_state_ttl_seconds)
        await self.session.commit()
        return redis_st, st.to_public_dict(), seat_events

    async def apply_player_action(
        self,
        user_id: UUID,
        table_id: str,
        action: BlackjackAction,
    ) -> tuple[dict, dict | None, list[dict]]:
        loaded = await load_table_state(self.redis, table_id)
        if loaded is None:
            raise ValueError("no_active_round")
        if loaded.user_id != user_id:
            raise ValueError("forbidden")

        st = loaded.to_multi()
        seat_events: list[dict] = []

        if st.phase == BlackjackPhase.finished:
            return st.to_public_dict(), None, seat_events

        if st.phase == BlackjackPhase.player_turn:
            human_idx = st.human_seat_index
            if st.active_seat_index != human_idx:
                raise ValueError("not_your_turn")
            apply_seat_action(st, human_idx, action)
            seat_events.append({
                "seat_index": human_idx,
                "action": action.value,
                "display_name": st.seats[human_idx].display_name,
            })

            if st.phase == BlackjackPhase.dealer_turn:
                post_human = advance_bot_turns(st, _bot_policy, stop_at_human=False)
                for idx, bot_action in post_human:
                    seat_events.append({
                        "seat_index": idx,
                        "action": bot_action.value,
                        "display_name": st.seats[idx].display_name,
                    })
                finish_dealer_and_settle(st)

        bonus_meta: dict | None = None
        if st.phase == BlackjackPhase.finished:
            bonus_meta = await self._finalize_round_db(
                st, loaded.session_id, user_id, table_id, WalletService(self.session)
            )
            await self.redis.delete(f"table:{table_id}:state")
            await self.session.commit()
            out = st.to_public_dict()
            if bonus_meta:
                out["retention"] = bonus_meta
            return out, bonus_meta, seat_events

        await save_table_state(
            self.redis,
            RedisTableState.from_multi(
                table_id, loaded.session_id, user_id, st, loaded.bot_count
            ),
            settings.table_state_ttl_seconds,
        )
        await self.session.commit()
        return st.to_public_dict(), None, seat_events

    async def _finalize_round_db(
        self,
        st: MultiSeatBlackjackState,
        session_id: UUID,
        user_id: UUID,
        table_id: str,
        wallet_svc: WalletService,
    ) -> dict | None:
        result_key, credit = human_settle_result(st)
        rr = RoundResult[result_key] if result_key in RoundResult.__members__ else RoundResult.draw
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise ValueError("no_wallet")
        if credit > 0:
            await wallet_svc.apply_amount(wallet.id, credit, TransactionType.win)

        bot_actions = [
            {"seat": s.display_name, "result": s.result, "hand": s.hand}
            for s in st.seats
            if not s.is_human
        ]
        self.session.add(
            Round(
                session_id=session_id,
                result=rr,
                payout_amount=credit,
                ai_actions={"table_id": table_id, "bots": bot_actions},
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
