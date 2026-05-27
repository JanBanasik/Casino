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
    SeatStatus,
    advance_bot_turns,
    advance_one_bot,
    apply_seat_action,
    dealer_draw_one,
    finish_dealer_and_settle,
    human_settle_result,
    new_multi_round,
)
from app.ml_inference.policies import make_default_policy
from app.schemas.table_lobby import TableLobby, load_table_lobby, save_table_lobby  # noqa: F401
from app.schemas.table_state import RedisTableState, load_table_state, save_table_state
from app.services.retention import RetentionService
from app.services.wallet import WalletService

_bot_policy = make_default_policy()


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

    def _lobby_seat_index(self, lobby: TableLobby, user_id: UUID) -> int | None:
        for i, occ in enumerate(lobby.seats):
            if occ is not None and occ.user_id == user_id:
                return i
        return None

    async def table_snapshot(self, user_id: UUID, table_id: str) -> dict:
        lobby = await load_table_lobby(self.redis, table_id)
        loaded = await load_table_state(self.redis, table_id)
        my_seat = self._lobby_seat_index(lobby, user_id)

        # Fill empty seats with ambient bots for atmosphere (display only, not saved)
        display_lobby = lobby.with_ambient_bots(table_id)

        if loaded is not None:
            st = loaded.to_multi()
            public = st.to_public_dict(table_phase="playing")
            public["lobby_seats"] = display_lobby.to_public()
            public["my_seat_index"] = my_seat
            public["round_in_progress"] = st.phase != BlackjackPhase.finished
            public["waiting_for_round"] = (
                my_seat is not None
                and loaded.user_id != user_id
                and st.phase != BlackjackPhase.finished
            )
            return public

        return {
            "table_phase": "idle",
            "phase": "idle",
            "player_hand": [],
            "dealer_hand": [],
            "dealer_hidden_count": 0,
            "bet": 0,
            "message": None,
            "active_seat_index": None,
            "human_seat_index": my_seat if my_seat is not None else 3,
            "seats": [],
            "lobby_seats": display_lobby.to_public(),
            "my_seat_index": my_seat,
            "round_in_progress": False,
            "waiting_for_round": False,
        }

    async def sit_at_table(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        seat_index: int,
    ) -> dict:
        if seat_index < 0 or seat_index > 6:
            raise ValueError("invalid_seat")

        gs = await self._get_session_owned(game_session_id, user_id)
        if gs is None:
            raise ValueError("session_not_found")

        lobby = await load_table_lobby(self.redis, table_id)
        if lobby.seats[seat_index] is not None and lobby.seats[seat_index].user_id != user_id:
            raise ValueError("seat_taken")

        for i, occ in enumerate(lobby.seats):
            if occ is not None and occ.user_id == user_id and i != seat_index:
                lobby.seats[i] = None

        username = await self._username(user_id)
        from app.schemas.table_lobby import LobbySeatOccupant

        lobby.seats[seat_index] = LobbySeatOccupant(
            user_id=user_id,
            session_id=game_session_id,
            display_name=username,
            avatar_key="you",
        )
        await save_table_lobby(self.redis, table_id, lobby, settings.table_state_ttl_seconds)

        loaded = await load_table_state(self.redis, table_id)
        waiting = loaded is not None and loaded.phase != BlackjackPhase.finished
        snap = await self.table_snapshot(user_id, table_id)
        if waiting:
            snap["waiting_for_round"] = True
            snap["message"] = "wait_round_end"
        return snap

    async def begin_round(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        bet: float,
        *,
        solo: bool = False,
        bot_count: int = 0,
    ) -> tuple[RedisTableState, dict, int]:
        """Deal cards and save initial state WITHOUT advancing any bots yet.
        Returns (redis_state, initial_public_dict, human_seat_index).
        """
        lobby = await load_table_lobby(self.redis, table_id)
        seat_idx = self._lobby_seat_index(lobby, user_id)
        if seat_idx is None:
            raise ValueError("not_seated")

        existing = await load_table_state(self.redis, table_id)
        if existing is not None and existing.phase != BlackjackPhase.finished:
            raise ValueError("round_in_progress")

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

        import random as _rnd
        st = new_multi_round(
            bet=bet,
            human_name=username,
            human_id=str(user_id),
            human_seat_index=seat_idx,
            bot_count=bot_count,
            rng=_rnd.Random(),
        )

        # Save state WITHOUT running bot turns (WS handler will do it incrementally)
        redis_st = RedisTableState.from_multi(table_id, game_session_id, user_id, st, bot_count)
        await save_table_state(self.redis, redis_st, settings.table_state_ttl_seconds)
        await self.session.commit()

        display_lobby = (await load_table_lobby(self.redis, table_id)).with_ambient_bots(table_id)
        public = st.to_public_dict(table_phase="playing")
        public["lobby_seats"] = display_lobby.to_public()
        public["my_seat_index"] = seat_idx
        public["round_in_progress"] = True

        total_players = sum(1 for s in st.seats if s.status != SeatStatus.empty)
        return redis_st, public, seat_idx, total_players

    async def advance_next_bot_step(
        self,
        user_id: UUID,
        table_id: str,
    ) -> tuple[dict, dict, bool] | None:
        """Advance exactly one bot seat.
        Returns (seat_event, new_public_dict, is_human_next) or None if human's turn / round over.
        """
        loaded = await load_table_state(self.redis, table_id)
        if loaded is None:
            return None

        st = loaded.to_multi()
        result = advance_one_bot(st, _bot_policy)
        if result is None:
            return None  # Human's turn

        idx, action = result
        seat = st.seats[idx]
        event = {
            "seat_index": idx,
            "action": action.value,
            "display_name": seat.display_name,
        }

        # Check if human is next or round ended
        is_human_next = (
            st.phase == BlackjackPhase.player_turn
            and st.active_seat_index == st.human_seat_index
        )
        round_done = st.phase == BlackjackPhase.finished

        if round_done:
            bonus = await self._finalize_round_db(
                st, loaded.session_id, user_id, table_id, WalletService(self.session)
            )
            await self.redis.delete(f"table:{table_id}:state")
            await self.session.commit()
        else:
            redis_st = RedisTableState.from_multi(table_id, loaded.session_id, user_id, st, loaded.bot_count)
            await save_table_state(self.redis, redis_st, settings.table_state_ttl_seconds)
            await self.session.commit()

        lobby = await load_table_lobby(self.redis, table_id)
        public = st.to_public_dict(table_phase="idle" if round_done else "playing")
        public["lobby_seats"] = lobby.with_ambient_bots(table_id).to_public()
        public["my_seat_index"] = self._lobby_seat_index(lobby, user_id)
        public["round_in_progress"] = not round_done

        return event, public, is_human_next or round_done

    async def dealer_step(
        self,
        user_id: UUID,
        table_id: str,
    ) -> tuple[dict, bool] | None:
        """Draw one dealer card. Returns (public_dict, is_done) or None if no active round."""
        from app.engine.blackjack import BlackjackPhase as _BjPhase
        loaded = await load_table_state(self.redis, table_id)
        if loaded is None:
            return None

        st = loaded.to_multi()
        if st.phase != _BjPhase.dealer_turn:
            return None

        done = dealer_draw_one(st)

        if done:
            finish_dealer_and_settle(st)
            bonus = await self._finalize_round_db(
                st, loaded.session_id, user_id, table_id, WalletService(self.session)
            )
            await self.redis.delete(f"table:{table_id}:state")
            await self.session.commit()
            lobby = await load_table_lobby(self.redis, table_id)
            public = st.to_public_dict(table_phase="idle")
            public["lobby_seats"] = lobby.with_ambient_bots(table_id).to_public()
            public["my_seat_index"] = self._lobby_seat_index(lobby, user_id)
            public["round_in_progress"] = False
            if bonus:
                public["retention"] = bonus
        else:
            redis_st = RedisTableState.from_multi(
                table_id, loaded.session_id, user_id, st, loaded.bot_count
            )
            await save_table_state(self.redis, redis_st, settings.table_state_ttl_seconds)
            await self.session.commit()
            lobby = await load_table_lobby(self.redis, table_id)
            public = st.to_public_dict(table_phase="playing")
            public["lobby_seats"] = lobby.with_ambient_bots(table_id).to_public()
            public["my_seat_index"] = self._lobby_seat_index(lobby, user_id)
            public["round_in_progress"] = True

        return public, done

    async def place_bet(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        bet: float,
        *,
        solo: bool = False,
        bot_count: int = 0,
    ) -> tuple[RedisTableState | None, dict, list[dict]]:
        """Start a round when table is idle; requires seated player."""
        lobby = await load_table_lobby(self.redis, table_id)
        seat_idx = self._lobby_seat_index(lobby, user_id)
        if seat_idx is None:
            raise ValueError("not_seated")

        existing = await load_table_state(self.redis, table_id)
        if existing is not None and existing.phase != BlackjackPhase.finished:
            raise ValueError("round_in_progress")

        return await self.new_round(
            user_id,
            game_session_id,
            table_id,
            bet,
            solo=solo,
            bot_count=bot_count,
            human_seat_index=seat_idx,
        )

    async def new_round(
        self,
        user_id: UUID,
        game_session_id: UUID,
        table_id: str,
        bet: float,
        *,
        solo: bool = False,
        bot_count: int = 0,
        human_seat_index: int = 3,
    ) -> tuple[RedisTableState | None, dict, list[dict]]:
        gs = await self._get_session_owned(game_session_id, user_id)
        if gs is None:
            raise ValueError("session_not_found")
        if gs.game_type != GameType.blackjack:
            raise ValueError("unsupported_game")

        existing = await load_table_state(self.redis, table_id)
        if existing is not None and existing.phase != BlackjackPhase.finished:
            raise ValueError("round_in_progress")

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
            human_seat_index=human_seat_index,
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
            public = st.to_public_dict(table_phase="idle")
            public["lobby_seats"] = (await load_table_lobby(self.redis, table_id)).to_public()
            public["my_seat_index"] = human_seat_index
            if bonus:
                public["retention"] = bonus
            return None, public, seat_events

        redis_st = RedisTableState.from_multi(table_id, game_session_id, user_id, st, bot_count)
        await save_table_state(self.redis, redis_st, settings.table_state_ttl_seconds)
        await self.session.commit()
        public = st.to_public_dict(table_phase="playing")
        public["lobby_seats"] = (await load_table_lobby(self.redis, table_id)).to_public()
        public["my_seat_index"] = human_seat_index
        public["round_in_progress"] = True
        return redis_st, public, seat_events

    async def apply_player_action(
        self,
        user_id: UUID,
        table_id: str,
        action: BlackjackAction,
    ) -> tuple[dict, dict | None, list[dict]]:
        loaded = await load_table_state(self.redis, table_id)
        if loaded is None:
            raise ValueError("no_active_round")

        st = loaded.to_multi()
        seat_events: list[dict] = []

        if st.phase == BlackjackPhase.finished:
            return st.to_public_dict(table_phase="idle"), None, seat_events

        if st.phase == BlackjackPhase.player_turn:
            human_idx = st.human_seat_index
            if st.active_seat_index != human_idx:
                raise ValueError("not_your_turn")
            human_seat = st.seats[human_idx]
            if human_seat.occupant_id != str(user_id):
                raise ValueError("forbidden")
            apply_seat_action(st, human_idx, action)
            seat_events.append({
                "seat_index": human_idx,
                "action": action.value,
                "display_name": st.seats[human_idx].display_name,
            })

            # NOTE: dealer phase is handled incrementally by the WS handler
            # (dealer_step method). Don't settle here — just save dealer_turn state.

        bonus_meta: dict | None = None
        if st.phase == BlackjackPhase.finished:
            bonus_meta = await self._finalize_round_db(
                st, loaded.session_id, user_id, table_id, WalletService(self.session)
            )
            await self.redis.delete(f"table:{table_id}:state")
            await self.session.commit()
            lobby = await load_table_lobby(self.redis, table_id)
            out = st.to_public_dict(table_phase="idle")
            out["lobby_seats"] = lobby.to_public()
            out["my_seat_index"] = self._lobby_seat_index(lobby, user_id)
            out["round_in_progress"] = False
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
        out = st.to_public_dict(table_phase="playing")
        out["lobby_seats"] = (await load_table_lobby(self.redis, table_id)).to_public()
        out["my_seat_index"] = self._lobby_seat_index(
            await load_table_lobby(self.redis, table_id), user_id
        )
        return out, None, seat_events

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
            if not s.is_human and s.status != SeatStatus.empty
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
