# SPDX-License-Identifier: Apache-2.0
"""Synthetic transfer graph with injected mule rings and benign look-alikes."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from vigil.network.graph import AccountMeta, Transfer

DAY = 86400.0
MONTH = 30 * DAY


@dataclass
class SyntheticNetwork:
    """Transfers, account metadata and ground truth."""

    transfers: list[Transfer] = field(default_factory=list)
    accounts: dict[str, AccountMeta] = field(default_factory=dict)
    mules: set[str] = field(default_factory=set)
    ring_of: dict[str, int] = field(default_factory=dict)
    hard_negatives: set[str] = field(default_factory=set)


def generate_network(
    n_accounts: int = 2500, n_rings: int = 12, seed: int = 7, mule_noise: float = 0.2
) -> SyntheticNetwork:
    """Builds a month of transfers.

    Contents: retail P2P traffic, merchants (many senders, slow payouts), payroll
    accounts (one old source, fast fan-out: a deliberate hard negative), charity
    collectors (many senders, no payout) and ``n_rings`` mule rings
    (victims -> entry -> layers -> cash-out) with partial benign activity.
    """
    rng = random.Random(seed)
    net = SyntheticNetwork()

    def add(aid: str, age: int, devices: tuple[str, ...] = (), merchant: bool = False) -> None:
        net.accounts[aid] = AccountMeta(aid, age, devices, merchant)

    users = [f"acc_{i:05d}" for i in range(n_accounts)]
    for u in users:
        age = rng.choice([rng.randrange(200, 3500)] * 9 + [rng.randrange(5, 90)])
        add(u, age, (f"dev_{u}",) if rng.random() > 0.05 else (f"dev_fam_{rng.randrange(60)}",))
    merchants = [f"mer_{i:03d}" for i in range(60)]
    for m in merchants:
        add(m, rng.randrange(300, 3000), (f"dev_{m}",), merchant=True)
    suppliers = [f"sup_{i:03d}" for i in range(20)]
    for s in suppliers:
        add(s, rng.randrange(500, 3000), (f"dev_{s}",))

    # Retail P2P.
    for u in users:
        for _ in range(max(1, int(rng.expovariate(1 / 6)))):
            dst = rng.choice(merchants) if rng.random() < 0.45 else rng.choice(users)
            if dst != u:
                net.transfers.append(
                    Transfer(u, dst, round(rng.lognormvariate(6.5, 1.0), 2), rng.uniform(0, MONTH))
                )

    # Merchants pay suppliers in lumps, hours-to-days later (not rapid pass-through).
    for m in merchants:
        for d in range(0, 30, 7):
            net.transfers.append(
                Transfer(
                    m,
                    rng.choice(suppliers),
                    round(rng.uniform(20000, 90000), 2),
                    d * DAY + rng.uniform(0.5, 3) * DAY,
                )
            )

    # Payroll: one old corporate source -> sudden fan-out within hours (hard negative).
    for k in range(15):
        corp, payroll = f"corp_{k:02d}", f"pay_{k:02d}"
        add(corp, 2500, (f"dev_{corp}",))
        add(payroll, rng.randrange(800, 3000), (f"dev_{payroll}",))
        net.hard_negatives.add(payroll)
        t0 = rng.uniform(1, 25) * DAY
        staff = rng.sample(users, rng.randrange(20, 60))
        net.transfers.append(Transfer(corp, payroll, 40000.0 * len(staff), t0))
        for s in staff:
            net.transfers.append(Transfer(payroll, s, 40000.0, t0 + rng.uniform(300, 5400)))

    # Charity / crowdfunding collectors: many senders, funds retained.
    for k in range(10):
        ch = f"charity_{k:02d}"
        add(ch, rng.randrange(400, 2500), (f"dev_{ch}",))
        net.hard_negatives.add(ch)
        for s in rng.sample(users, rng.randrange(30, 120)):
            net.transfers.append(
                Transfer(s, ch, round(rng.uniform(100, 5000), 2), rng.uniform(0, MONTH))
            )

    # Resellers / informal traders: many senders, forward quickly, but old accounts
    # with long histories. A deliberate, confusable hard negative.
    for k in range(14):
        rs, sup = f"reseller_{k:02d}", rng.choice(suppliers)
        add(rs, rng.randrange(400, 2500), (f"dev_{rs}",))
        net.hard_negatives.add(rs)
        for _ in range(rng.randrange(12, 40)):
            amt, ts = round(rng.uniform(500, 8000), 2), rng.uniform(0, MONTH)
            net.transfers.append(Transfer(rng.choice(users), rs, amt, ts))
            if rng.random() < 0.7:
                net.transfers.append(
                    Transfer(rs, sup, round(amt * 0.97, 2), ts + rng.uniform(600, 5400))
                )

    # Mule rings.
    for r in range(n_rings):
        size = rng.randrange(4, 11)
        members = [f"mule_{r:02d}_{i:02d}" for i in range(size)]
        shared = [f"dev_ring_{r}_{j}" for j in range(rng.choice([1, 2]))]
        for m in members:
            age = rng.choice(
                [rng.randrange(3, 30)] * 6 + [rng.randrange(30, 90)] * 3 + [rng.randrange(200, 900)]
            )
            devs = (rng.choice(shared),) if rng.random() < 0.55 else (f"dev_{m}",)
            add(m, age, devs)
            net.mules.add(m)
            net.ring_of[m] = r
        n_entry = max(1, size // 4)
        entry, rest = members[:n_entry], members[n_entry:]
        layer2 = rest[: max(1, len(rest) // 2)]
        cash = rest[len(layer2) :] or layer2
        start = rng.uniform(1, 20) * DAY
        for e in entry:
            for _ in range(rng.randrange(10, 50)):
                victim = rng.choice(users)
                ts = start + rng.uniform(0, rng.uniform(6, 48) * 3600)
                amt = round(rng.uniform(2000, 150000), 2)
                net.transfers.append(Transfer(victim, e, amt, ts))
                nxt = rng.choice(layer2)
                keep = rng.uniform(0.0, 0.08)
                net.transfers.append(
                    Transfer(
                        e,
                        nxt,
                        round(amt * (1 - keep), 2),
                        ts + rng.uniform(120, 3000 if rng.random() > 0.25 else 9000),
                    )
                )
        for l2 in layer2:
            inflow = [t for t in net.transfers if t.dst == l2]
            for t in inflow:
                dst = rng.choice(cash) if cash else l2
                if dst != l2:
                    net.transfers.append(
                        Transfer(
                            l2,
                            dst,
                            round(t.amount * 0.95, 2),
                            t.ts + rng.uniform(300, 3600 if rng.random() > 0.25 else 9000),
                        )
                    )
        for c in cash:
            sink = f"ext_{r:02d}_{rng.randrange(3)}"
            if sink not in net.accounts:
                add(sink, 400, (f"dev_{sink}",))
            for t in [t for t in net.transfers if t.dst == c]:
                net.transfers.append(
                    Transfer(c, sink, round(t.amount * 0.97, 2), t.ts + rng.uniform(300, 3600))
                )
        # Some mules also have ordinary-looking activity.
        for m in members:
            if rng.random() < mule_noise:
                for _ in range(rng.randrange(1, 5)):
                    net.transfers.append(
                        Transfer(
                            m,
                            rng.choice(users),
                            round(rng.uniform(100, 2000), 2),
                            rng.uniform(0, MONTH),
                        )
                    )

    net.transfers.sort(key=lambda t: t.ts)
    return net
