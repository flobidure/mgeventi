#!/usr/bin/env python3
"""Calculateur de risque avec effet de levier : liquidation, frais, risque de ruine.

Conçu pour les petits comptes à fort levier (crypto/forex/CFD). Met en évidence
les trois pièges mortels : liquidation avant le stop, frais sur le notional, et
risque de ruine. Tous les frais se calculent sur le NOTIONAL (capital × levier),
pas sur la marge.
"""
import argparse


def liquidation(equity, leverage, entry, side, maintenance_pct, fee_bps):
    """Distance approximative à la liquidation (modèle isolé simplifié)."""
    # Le compte est liquidé quand la perte ≈ marge - marge de maintenance.
    # Distance en fraction de prix ≈ (1/levier) - maintenance - frais d'ouverture.
    fee_frac = fee_bps / 1e4
    move_to_liq = 1 / leverage - maintenance_pct / 100 - fee_frac
    move_to_liq = max(move_to_liq, 0.0)
    if side == "long":
        liq_price = entry * (1 - move_to_liq)
    else:
        liq_price = entry * (1 + move_to_liq)
    return move_to_liq, liq_price


def cmd_leverage(a):
    notional = a.equity * a.leverage
    fee_round_trip = notional * (a.fee_bps / 1e4) * 2
    move_liq, liq_price = liquidation(a.equity, a.leverage, a.entry, a.side,
                                      a.maintenance, a.fee_bps)

    print("\n=== Position avec levier ===")
    print(f"  Capital (marge)            {a.equity:>12,.2f} €")
    print(f"  Levier                     {a.leverage:>12}x")
    print(f"  Notional (exposition)      {notional:>12,.2f} €")
    print(f"  Prix d'entrée              {a.entry:>12,.4f}  ({a.side})")
    print("\n=== Liquidation ===")
    print(f"  Mouvement avant liquidation{move_liq * 100:>11.3f} %")
    print(f"  Prix de liquidation        {liq_price:>12,.4f}")
    print("\n=== Frais (sur le notional !) ===")
    print(f"  Frais aller-retour         {fee_round_trip:>12,.2f} €")
    print(f"  ... soit en % du capital   {fee_round_trip / a.equity * 100:>11.1f} %")

    if a.stop is not None:
        stop_move = abs(a.entry - a.stop) / a.entry
        loss_at_stop = notional * stop_move + fee_round_trip
        print("\n=== Stop ===")
        print(f"  Distance du stop           {stop_move * 100:>11.3f} %")
        print(f"  Perte au stop (frais incl.){loss_at_stop:>12,.2f} €  "
              f"({loss_at_stop / a.equity * 100:.1f} % du capital)")
        if stop_move >= move_liq:
            print("\n  ⚠️  STOP AU-DELÀ DE LA LIQUIDATION : tu es liquidé AVANT que ton")
            print("      stop ne se déclenche. Ta gestion du risque est inopérante.")
            print(f"      → Réduis le levier sous {1 / (stop_move + a.maintenance / 100 + a.fee_bps / 1e4):.0f}x"
                  f" pour que le stop tienne.")
        else:
            print("\n  ✓ Le stop se déclenche avant la liquidation (config viable côté liquidation).")


def cmd_safe_leverage(a):
    """Levier maximal pour qu'un stop à `stop_pct` % tienne avant liquidation, en risquant `risk_pct` %."""
    fee_frac = a.fee_bps / 1e4
    stop_frac = a.stop_pct / 100
    # 1) contrainte de liquidation : stop_frac < 1/L - maint - fee  =>  L < 1/(stop_frac+maint+fee)
    max_lev_liq = 1 / (stop_frac + a.maintenance / 100 + fee_frac)
    # 2) contrainte de risque : perte au stop = notional*stop_frac = equity*L*stop_frac <= equity*risk
    #    => L <= risk_frac / stop_frac  (frais en sus, on les ajoute)
    risk_frac = a.risk_pct / 100
    max_lev_risk = risk_frac / stop_frac
    safe = min(max_lev_liq, max_lev_risk)

    print("\n=== Levier soutenable ===")
    print(f"  Capital                    {a.equity:>12,.2f} €")
    print(f"  Stop visé                  {a.stop_pct:>11.2f} %")
    print(f"  Risque max par trade       {a.risk_pct:>11.2f} %  ({a.equity * risk_frac:.2f} €)")
    print("-" * 48)
    print(f"  Levier max (liquidation)   {max_lev_liq:>11.1f}x")
    print(f"  Levier max (risque {a.risk_pct:.0f}%)     {max_lev_risk:>11.1f}x")
    print(f"  → LEVIER RECOMMANDÉ         {safe:>11.1f}x  (le plus prudent des deux)")
    print(f"\n  À {safe:.1f}x : notional {a.equity * safe:,.0f} €, "
          f"perte au stop ≈ {a.equity * safe * stop_frac:,.2f} €.")


def cmd_ruin(a):
    """Estime le nombre de pertes consécutives jusqu'à la ruine et le risque de ruine (Kelly négatif)."""
    risk_frac = a.risk_pct / 100
    # pertes consécutives pour passer sous le seuil de ruine
    equity, n = 1.0, 0
    while equity > a.ruin_level / 100 and n < 1000:
        equity *= (1 - risk_frac)
        n += 1
    print("\n=== Risque de ruine ===")
    print(f"  Risque par trade           {a.risk_pct:>11.2f} %")
    print(f"  Pertes consécutives → ruine{n:>11}  (compte sous {a.ruin_level:.0f}% du capital)")
    if a.win_rate is not None and a.rr is not None:
        p = a.win_rate / 100
        # risque de ruine (approx, mises fixes) via formule du joueur
        edge = p * a.rr - (1 - p)
        if edge <= 0:
            print(f"  Espérance par trade        NÉGATIVE ({edge:.3f} R) → ruine quasi certaine à long terme.")
        else:
            # approximation : RoR ≈ ((1-edge_adj)/(1+edge_adj))^(capital/mise)
            q_over_p = (1 - p) / (p * a.rr) if p * a.rr > 0 else 1
            units = 1 / risk_frac
            ror = q_over_p ** units if q_over_p < 1 else 1.0
            print(f"  Espérance par trade        +{edge:.3f} R")
            print(f"  Risque de ruine (approx)   {min(ror, 1) * 100:>11.2f} %")


def main():
    p = argparse.ArgumentParser(description="Calculateur de risque avec levier.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("position", help="Analyse une position à levier (liquidation, frais, stop).")
    pl.add_argument("--equity", type=float, required=True, help="Capital / marge en €.")
    pl.add_argument("--leverage", type=int, required=True)
    pl.add_argument("--entry", type=float, required=True)
    pl.add_argument("--stop", type=float)
    pl.add_argument("--side", choices=["long", "short"], default="long")
    pl.add_argument("--fee-bps", type=float, default=4)
    pl.add_argument("--maintenance", type=float, default=0.5, help="Marge de maintenance en %.")
    pl.set_defaults(func=cmd_leverage)

    ps = sub.add_parser("safe", help="Levier soutenable pour un stop et un risque donnés.")
    ps.add_argument("--equity", type=float, required=True)
    ps.add_argument("--stop-pct", type=float, required=True, help="Distance du stop en %.")
    ps.add_argument("--risk-pct", type=float, default=1, help="Risque max par trade en %.")
    ps.add_argument("--fee-bps", type=float, default=4)
    ps.add_argument("--maintenance", type=float, default=0.5)
    ps.set_defaults(func=cmd_safe_leverage)

    pr = sub.add_parser("ruin", help="Risque de ruine selon le risque par trade.")
    pr.add_argument("--risk-pct", type=float, required=True)
    pr.add_argument("--ruin-level", type=float, default=20, help="Seuil de ruine en % du capital initial.")
    pr.add_argument("--win-rate", type=float, help="Taux de réussite en %.")
    pr.add_argument("--rr", type=float, help="Ratio gain/perte (R).")
    pr.set_defaults(func=cmd_ruin)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
