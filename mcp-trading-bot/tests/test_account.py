import pytest

from trading_bot.account import PaperAccount, RejectedOrder
from trading_bot.config import Settings


@pytest.fixture
def account(tmp_path):
    settings = Settings(data_dir=tmp_path, start_balance=50_000, symbol_whitelist=["MES", "MNQ"])
    acct = PaperAccount(settings)
    acct.on_price("MES", 5000.0)
    return acct


def test_rejects_order_without_reasoning(account):
    with pytest.raises(RejectedOrder, match="reasoning"):
        account.enter("long", "MES", 1, stop=4995.0, reasoning="  ")


def test_rejects_symbol_off_whitelist(account):
    with pytest.raises(RejectedOrder, match="whitelist"):
        account.enter("long", "BTCUSD", 1, stop=4995.0, reasoning="test")


def test_rejects_wrong_side_stop(account):
    with pytest.raises(RejectedOrder, match="below entry"):
        account.enter("long", "MES", 1, stop=5001.0, reasoning="test")
    with pytest.raises(RejectedOrder, match="above entry"):
        account.enter("short", "MES", 1, stop=4999.0, reasoning="test")


def test_rejects_without_market_data(tmp_path):
    settings = Settings(data_dir=tmp_path, symbol_whitelist=["MES"])
    acct = PaperAccount(settings)
    with pytest.raises(RejectedOrder, match="no market data"):
        acct.enter("long", "MES", 1, stop=4995.0, reasoning="test")


def test_rejects_oversize(account):
    with pytest.raises(RejectedOrder, match="between 1 and"):
        account.enter("long", "MES", 99, stop=4995.0, reasoning="test")


def test_one_position_at_a_time(account):
    account.enter("long", "MES", 1, stop=4995.0, reasoning="first")
    with pytest.raises(RejectedOrder, match="one position at a time"):
        account.enter("short", "MNQ", 1, stop=5005.0, reasoning="second")


def test_stop_hit_closes_at_stop_with_minus_one_r(account):
    account.enter("long", "MES", 2, stop=4995.0, target=5010.0, reasoning="test entry")
    closed = account.on_price("MES", 4994.0)
    assert closed is not None
    assert closed.exit_price == 4995.0
    assert closed.pnl == -50.0  # 5 points * $5 * 2 contracts
    assert closed.r_multiple == -1.0
    assert account.position is None
    assert account.balance == 49_950.0


def test_target_hit_closes_at_target(account):
    account.enter("long", "MES", 1, stop=4995.0, target=5010.0, reasoning="test entry")
    closed = account.on_price("MES", 5012.0)
    assert closed is not None
    assert closed.exit_price == 5010.0
    assert closed.pnl == 50.0
    assert closed.r_multiple == 2.0


def test_short_pnl_and_manual_close(account):
    account.enter("short", "MES", 1, stop=5005.0, reasoning="short entry")
    account.on_price("MES", 4990.0)
    trade = account.close("Closing into support per rule 2.3.")
    assert trade.pnl == 50.0  # 10 points * $5
    assert trade.exit_reasoning.startswith("Closing into support")


def test_modify_stop_validates_side(account):
    account.enter("long", "MES", 1, stop=4995.0, reasoning="entry")
    with pytest.raises(RejectedOrder, match="below current price"):
        account.modify_stop(5002.0, "trail")
    pos = account.modify_stop(4998.0, "trail behind 1-min BOS")
    assert pos.stop == 4998.0
    assert pos.initial_stop == 4995.0  # R math keeps using the initial stop


def test_flatten_on_kill_switch(account):
    account.enter("long", "MES", 1, stop=4995.0, reasoning="entry")
    trade = account.flatten("Kill switch.")
    assert trade is not None
    assert account.position is None


def test_state_persists_across_reload(tmp_path):
    settings = Settings(data_dir=tmp_path, symbol_whitelist=["MES"])
    acct = PaperAccount(settings)
    acct.on_price("MES", 5000.0)
    acct.enter("long", "MES", 1, stop=4995.0, reasoning="persist me")
    reloaded = PaperAccount(settings)
    assert reloaded.position is not None
    assert reloaded.position.reasoning == "persist me"
    assert reloaded.last_price["MES"] == 5000.0
