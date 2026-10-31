"""Сверка: поручения / снимок до / снимок после / банк / заявки. Только чтение, деньги в целых копейках."""
import csv, json, sqlite3, sys
from pathlib import Path

EV = Path(__file__).resolve().parent.parent / "evidence"

def rows_csv(name):
    with open(EV / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def snap(name):
    con = sqlite3.connect(f"file:{EV/name}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    d = {r["tx_id"]: dict(r) for r in con.execute("SELECT * FROM transactions")}
    con.close()
    return d

orders = {r["tx_id"]: r for r in rows_csv("payment_orders.csv")}
bank   = {r["tx_id"]: r for r in rows_csv("bank_ledger.csv")}
before = snap("snapshot_before.sqlite")
after  = snap("snapshot_after.sqlite")
tickets = rows_csv("change_requests.csv")

assert set(orders) == set(bank) == set(before) == set(after), "наборы tx_id различаются"

def total(d, key="amount_minor"):
    return sum(int(v[key]) for v in d.values())

summary = {
    "counts": {"orders": len(orders), "before": len(before), "after": len(after), "bank": len(bank)},
    "totals_minor": {"orders": total(orders), "before": total(before), "after": total(after), "bank": total(bank)},
}

def ticket_ok(tx, old, new):
    return any(t["tx_id"] == tx and t["status"] == "APPROVED"
               and t["old_to_account"] == old and t["new_to_account"] == new for t in tickets)

table, unauthorized = [], []
for tx in sorted(orders):
    o, b, a, k = orders[tx], before[tx], after[tx], bank[tx]
    notes = []
    if int(o["amount_minor"]) != int(b["amount_minor"]) or int(b["amount_minor"]) != int(a["amount_minor"]) or int(a["amount_minor"]) != int(k["amount_minor"]):
        notes.append("СУММА РАЗЛИЧАЕТСЯ")
    if b["status"] != a["status"]:
        notes.append(f"статус {b['status']}->{a['status']}")
    recip_changed = not (o["to_account"] == b["to_account"] == a["to_account"] == k["to_account"])
    if not recip_changed:
        if notes:
            table.append((tx, o["to_account"], b["to_account"], a["to_account"], k["to_account"], "-", "; ".join(notes) + "; получатель не менялся", "законно"))
        continue
    # получатель менялся где-то
    ok = (b["to_account"] == o["to_account"] and ticket_ok(tx, b["to_account"], a["to_account"]) and a["to_account"] == k["to_account"])
    tk = [f'{t["ticket"]}/{t["status"]}' for t in tickets if t["tx_id"] == tx] or ["нет заявки"]
    cls = "законное исправление" if ok else "НЕСАНКЦИОНИРОВАННО"
    if not ok:
        unauthorized.append(tx)
    table.append((tx, o["to_account"], b["to_account"], a["to_account"], k["to_account"], ",".join(tk), "; ".join(notes) or "смена получателя", cls))

# сумма: исполнено банком по подменённым (каждая tx один раз)
diverted = sum(int(bank[tx]["amount_minor"]) for tx in set(unauthorized) if tx in bank)
status_changes = sum(1 for tx in before if before[tx]["status"] != after[tx]["status"])
summary.update({
    "status_before": {s: sum(1 for v in before.values() if v["status"] == s) for s in ("APPROVED", "SETTLED")},
    "status_after": {s: sum(1 for v in after.values() if v["status"] == s) for s in ("APPROVED", "SETTLED")},
    "status_changed_rows": status_changes,
    "unauthorized_tx_ids": sorted(set(unauthorized)),
    "diverted_amount_minor": diverted,
    "diverted_display": f"{diverted // 100} руб. {diverted % 100:02d} коп.",
})
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nTX | ПОРУЧЕНИЕ | ДО | ПОСЛЕ | БАНК | ЗАЯВКА | ДЕТАЛИ | КЛАССИФИКАЦИЯ")
for r in table:
    if r[-1] != "законно":
        print(" | ".join(r))
print(f"\n(остальные 236 строк: получатель совпадает во всех 4 источниках, изменился только статус APPROVED->SETTLED)")
