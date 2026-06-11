from __future__ import annotations

import random
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.table_limits import poker_table_blinds
from app.db.models import GameSession, Round, RoundResult, TransactionType, User
from app.engine.poker import (
    PokerAction,
    PokerPhase,
    advance_poker_bots,
    apply_poker_action,
    new_poker_round,
)
from app.ml_inference.registry import get_poker_policy
from app.schemas.poker_state import (
    RedisPokerState,
    load_poker_state,
    save_poker_state,
)
from app.schemas.table_lobby import TableLobby, load_table_lobby, save_table_lobby
from app.services.bonus import BonusService
from app.services.payouts import boost_credit
from app.services.wallet import WalletService


class PokerRoundService:
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

    def _lobby_seat_index(self, lobby: TableLobby, user_id: UUID) -> int | None:
        for i, occ in enumerate(lobby.seats):
            if occ is not None and not occ.is_bot and occ.user_id == user_id:
                return i
        return None

    async def table_snapshot(self, user_id: UUID, table_id: str) -> dict:
        lobby = await load_table_lobby(self.redis, table_id)
        loaded = await load_poker_state(self.redis, table_id)
        my_seat = self._lobby_seat_index(lobby, user_id)
        display_lobby = lobby.with_ambient_bots(table_id)

        if loaded is not None:
            st = loaded.to_poker()
            public = st.to_public_dict(table_phase="playing")
            public["lobby_seats"] = display_lobby.to_public()
            public["my_seat_index"] = my_seat
            public["round_in_progress"] = st.phase not in (PokerPhase.showdown, PokerPhase.finished)
            return public

        small_blind, big_blind = poker_table_blinds(table_id)
        return {
            "table_phase": "idle",
            "phase": "waiting",
            "community_cards": [],
            "hole_cards": [],
            "pot": 0,
            "current_bet": 0,
            "min_raise": big_blind,
            "active_seat_index": None,
            "dealer_seat_index": 0,
            "human_seat_index": my_seat if my_seat is not None else 0,
            "small_blind": small_blind,
            "big_blind": big_blind,
            "message": None,
            "seats": [],
            "lobby_seats": display_lobby.to_public(),
            "my_seat_index": my_seat,
            "round_in_progress": False,
        }

    async def sit_at_table(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        seat_index: int,
    ) -> dict:
        if seat_index < 0 or seat_index > 5:
            raise ValueError("invalid_seat")

        gs = await self._get_session_owned(game_session_id, user_id)
        if gs is None:
            raise ValueError("session_not_found")

        lobby = await load_table_lobby(self.redis, table_id)
        real_occ = [s for s in lobby.seats if s is not None and not s.is_bot]
        seat_free_or_other = (
            lobby.seats[seat_index] is None or lobby.seats[seat_index].user_id != user_id
        )
        if any(s.user_id == user_id for s in real_occ if seat_free_or_other):
            pass  # allow re-sit

        # Remove old seat for this user
        for i, occ in enumerate(lobby.seats):
            if occ is not None and not occ.is_bot and occ.user_id == user_id and i != seat_index:
                lobby.seats[i] = None

        # Check seat not taken by real player
        existing = lobby.seats[seat_index]
        if existing is not None and not existing.is_bot and existing.user_id != user_id:
            raise ValueError("seat_taken")

        from app.schemas.table_lobby import LobbySeatOccupant
        username = await self._username(user_id)
        lobby.seats[seat_index] = LobbySeatOccupant(
            user_id=user_id,
            session_id=game_session_id,
            display_name=username,
            avatar_key="you",
            is_bot=False,
        )
        await save_table_lobby(self.redis, table_id, lobby, settings.table_state_ttl_seconds)
        return await self.table_snapshot(user_id, table_id)

    async def start_hand(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        buy_in: float,
        bot_count: int = 2,
        difficulty: str = "medium",
    ) -> tuple[RedisPokerState | None, dict, list[dict]]:
        lobby = await load_table_lobby(self.redis, table_id)
        seat_idx = self._lobby_seat_index(lobby, user_id)
        if seat_idx is None:
            raise ValueError("not_seated")

        existing = await load_poker_state(self.redis, table_id)
        if existing is not None and existing.phase not in (
            PokerPhase.showdown,
            PokerPhase.finished,
        ):
            raise ValueError("hand_in_progress")

        gs = await self._get_session_owned(game_session_id, user_id)
        if gs is None:
            raise ValueError("session_not_found")

        small_blind, big_blind = poker_table_blinds(table_id)
        # Must at least cover the big blind, and never below the global floor.
        min_buyin = max(settings.poker_min_buyin, big_blind)
        if buy_in < min_buyin:
            raise ValueError("buyin_below_minimum")
        if buy_in > settings.poker_max_buyin:
            raise ValueError("buyin_above_maximum")

        wallet_svc = WalletService(self.session)
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise ValueError("no_wallet")
        if wallet.balance < buy_in:
            raise ValueError("insufficient_balance")

        await wallet_svc.apply_amount(wallet.id, -buy_in, TransactionType.bet)
        username = await self._username(user_id)
        bot_count = max(1, min(bot_count, 5))

        st = new_poker_round(
            human_name=username,
            human_id=str(user_id),
            human_seat_index=seat_idx,
            bot_count=bot_count,
            buy_in=buy_in,
            small_blind=small_blind,
            big_blind=big_blind,
            rng=random.Random(),
        )

        seat_events: list[dict] = []
        pre_events = advance_poker_bots(st, get_poker_policy(difficulty))
        for idx, action, amount in pre_events:
            seat_events.append({
                "seat_index": idx,
                "action": action.value,
                "amount": amount,
                "display_name": st.seats[idx].display_name,
            })

        if st.phase in (PokerPhase.finished,):
            bonus = await self._finalize_hand_db(
                st, game_session_id, user_id, wallet_svc, difficulty
            )
            await self.session.commit()
            display_lobby = lobby.with_ambient_bots(table_id)
            public = st.to_public_dict(table_phase="idle")
            public["phase"] = "waiting"
            public["lobby_seats"] = display_lobby.to_public()
            public["my_seat_index"] = seat_idx
            public["round_in_progress"] = False
            if bonus:
                public["retention"] = bonus
            return None, public, seat_events

        redis_st = RedisPokerState.from_poker(
            table_id, game_session_id, user_id, st, bot_count, difficulty
        )
        await save_poker_state(self.redis, redis_st, settings.table_state_ttl_seconds)
        await self.session.commit()
        display_lobby = lobby.with_ambient_bots(table_id)
        public = st.to_public_dict(table_phase="playing")
        public["lobby_seats"] = display_lobby.to_public()
        public["my_seat_index"] = seat_idx
        public["round_in_progress"] = True
        return redis_st, public, seat_events

    async def apply_action(
        self,
        user_id: UUID,
        table_id: str,
        action: PokerAction,
        raise_amount: float = 0.0,
    ) -> tuple[dict, list[dict]]:
        loaded = await load_poker_state(self.redis, table_id)
        if loaded is None:
            raise ValueError("no_active_hand")
        if loaded.user_id != user_id:
            raise ValueError("forbidden")

        st = loaded.to_poker()
        seat_events: list[dict] = []

        if st.phase in (PokerPhase.finished, PokerPhase.showdown):
            lobby = await load_table_lobby(self.redis, table_id)
            out = st.to_public_dict(table_phase="idle")
            out["phase"] = "waiting"
            out["round_in_progress"] = False
            return out, seat_events

        human_idx = st.human_seat_index
        if st.active_seat_index != human_idx:
            raise ValueError("not_your_turn")

        apply_poker_action(st, human_idx, action, raise_amount)
        seat_events.append({
            "seat_index": human_idx,
            "action": action.value,
            "amount": raise_amount,
            "display_name": st.seats[human_idx].display_name,
        })

        # Advance bots after human action
        bot_events = advance_poker_bots(st, get_poker_policy(loaded.difficulty))
        for idx, bot_action, amount in bot_events:
            seat_events.append({
                "seat_index": idx,
                "action": bot_action.value,
                "amount": amount,
                "display_name": st.seats[idx].display_name,
            })

        lobby = await load_table_lobby(self.redis, table_id)
        display_lobby = lobby.with_ambient_bots(table_id)

        if st.phase in (PokerPhase.finished,):
            await self.redis.delete(f"poker:{table_id}:state")
            bonus = await self._finalize_hand_db(
                st, loaded.session_id, user_id, WalletService(self.session), loaded.difficulty
            )
            await self.session.commit()
            out = st.to_public_dict(table_phase="idle")
            out["phase"] = "waiting"
            out["lobby_seats"] = display_lobby.to_public()
            out["my_seat_index"] = self._lobby_seat_index(lobby, user_id)
            out["round_in_progress"] = False
            if bonus:
                out["retention"] = bonus
            return out, seat_events

        updated = RedisPokerState.from_poker(
            table_id, loaded.session_id, user_id, st, loaded.bot_count, loaded.difficulty
        )
        await save_poker_state(self.redis, updated, settings.table_state_ttl_seconds)
        await self.session.commit()
        out = st.to_public_dict(table_phase="playing")
        out["lobby_seats"] = display_lobby.to_public()
        out["my_seat_index"] = self._lobby_seat_index(lobby, user_id)
        return out, seat_events

    async def _finalize_hand_db(
        self,
        st,
        session_id: UUID,
        user_id: UUID,
        wallet_svc: WalletService,
        difficulty: str = "medium",
    ) -> dict | None:
        human = st.human_seat()
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            return None

        # The buy-in was debited up front, so at hand end we cash out the player's
        # whole remaining stack — NOT just the pot they won. Otherwise folding (or
        # any hand where you don't commit your full stack) would forfeit the
        # unbet chips. Every seat starts the hand with the buy-in, so:
        #   buy_in = final_chips + committed - pot_won
        buy_in = human.chips + human.bet_total - human.payout
        # Cash out, boosting only the winning profit by the table's multiplier.
        final_credit = boost_credit(human.chips, buy_in, difficulty)
        human.chips = final_credit  # show the cashed-out stack at the table
        if final_credit > 0:
            await wallet_svc.apply_amount(wallet.id, final_credit, TransactionType.win)

        result_key = human.result or "loss"
        rr = RoundResult[result_key] if result_key in RoundResult.__members__ else RoundResult.draw
        # Record the hand result: stake = chips committed, payout = boosted pot win,
        # so history net (payout − bet) equals the player's net result.
        boosted_winnings = boost_credit(human.payout, human.bet_total, difficulty)
        human.payout = boosted_winnings
        bot_info = [
            {"seat": s.display_name, "result": s.result, "hand": s.hole_cards}
            for s in st.seats
            if not s.is_human and s.status.value != "empty"
        ]
        self.session.add(Round(
            session_id=session_id,
            result=rr,
            payout_amount=boosted_winnings,
            bet_amount=human.bet_total,
            ai_actions={"game": "poker", "bots": bot_info},
        ))
        await self.session.flush()

        bonus = BonusService(self.session)
        return await bonus.settle_post_round(
            user_id, wallet_svc, was_loss=rr == RoundResult.loss
        )
